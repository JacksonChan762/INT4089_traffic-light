"""Decode browser frames and count model cars on the host computer."""

from collections import OrderedDict
import re
from threading import BoundedSemaphore, Lock
from time import monotonic

import cv2
import numpy as np

from .detector import count_objects


CAMERA_ROUTES = ('/api/camera/background', '/api/camera/analyze')
MAX_JPEG_BYTES = 512 * 1024
MAX_DIMENSION = 640
BACKGROUND_TTL = 300
MAX_BACKGROUNDS = 8
SESSION_PATTERN = re.compile(r'[0-9a-f]{32}')
ROAD_PATTERN = re.compile(r'[0-9]{1,3}(,[0-9]{1,3}){3}')
INTEGER_PATTERN = re.compile(r'[0-9]{1,5}')


class CameraError(ValueError):
    def __init__(self, reason, status=400):
        super().__init__(reason)
        self.status = status


def jpeg_size(data):
    # Check the JPEG size before letting OpenCV allocate a decoded image.
    if data[:2] != b'\xff\xd8':
        raise CameraError('Expected a JPEG camera frame')
    offset = 2
    while offset < len(data) and data[offset] == 0xff:
        while offset < len(data) and data[offset] == 0xff:
            offset += 1
        if offset + 3 > len(data):
            break
        marker = data[offset]
        offset += 1
        length = int.from_bytes(data[offset:offset + 2], 'big')
        if length < 2 or offset + length > len(data) or marker in (0xda, 0xd9):
            break
        if 0xc0 <= marker <= 0xcf and marker not in (0xc4, 0xc8, 0xcc):
            if marker not in (0xc0, 0xc2) or length < 8:
                break
            height = int.from_bytes(data[offset + 3:offset + 5], 'big')
            width = int.from_bytes(data[offset + 5:offset + 7], 'big')
            if not (10 <= height <= MAX_DIMENSION and 10 <= width <= MAX_DIMENSION):
                raise CameraError('Camera frame dimensions must be 10–640 pixels')
            return width, height
        offset += length
    raise CameraError('Invalid JPEG camera frame')


def decode_frame(data):
    width, height = jpeg_size(data)
    try:
        frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8),
                             cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    except cv2.error as error:
        raise CameraError('Cannot decode the JPEG camera frame') from error
    if frame is None or frame.shape != (height, width, 3):
        raise CameraError('Cannot decode the JPEG camera frame')
    return frame


def header(headers, name, pattern):
    values = headers.get_all(name, [])
    if len(values) != 1 or not pattern.fullmatch(values[0]):
        raise CameraError(f'Invalid {name} header')
    return values[0]


def integer_header(headers, name, maximum):
    value = int(header(headers, name, INTEGER_PATTERN))
    if not 1 <= value <= maximum:
        raise CameraError(f'{name} must be between 1 and {maximum}')
    return value


def read_roads(headers, shape):
    height, width, _ = shape
    roads = tuple(tuple(map(int, header(headers, f'X-Road-{road}', ROAD_PATTERN).split(',')))
                  for road in ('A', 'B'))
    for x, y, w, h in roads:
        if w < 10 or h < 10 or x + w > width or y + h > height:
            raise CameraError('Road areas must be inside the preview and at least 10 by 10 pixels')
    (ax, ay, aw, ah), (bx, by, bw, bh) = roads
    if max(ax, bx) < min(ax + aw, bx + bw) and max(ay, by) < min(ay + ah, by + bh):
        raise CameraError('Road areas must not overlap')
    return roads


class CameraAnalysis:
    def __init__(self):
        self.backgrounds = OrderedDict()
        self.lock = Lock()
        self.workers = BoundedSemaphore(2)

    def prune(self, now):
        while self.backgrounds:
            _, used = next(iter(self.backgrounds.values()))
            if now - used < BACKGROUND_TTL:
                break
            self.backgrounds.popitem(last=False)

    def expire(self):
        with self.lock:
            self.prune(monotonic())

    def remember(self, session, frame):
        with self.lock:
            now = monotonic()
            self.prune(now)
            self.backgrounds[session] = (frame, now)
            self.backgrounds.move_to_end(session)
            if len(self.backgrounds) > MAX_BACKGROUNDS:
                self.backgrounds.popitem(last=False)

    def background(self, session):
        with self.lock:
            now = monotonic()
            self.prune(now)
            if session not in self.backgrounds:
                raise CameraError('Capture an empty-road background first', 409)
            frame, _ = self.backgrounds[session]
            self.backgrounds[session] = (frame, now)
            self.backgrounds.move_to_end(session)
            return frame

    def process(self, path, headers, data):
        session = header(headers, 'X-Camera-Session', SESSION_PATTERN)
        if headers.get_content_type() != 'image/jpeg':
            raise CameraError('Expected image/jpeg', 415)
        if not self.workers.acquire(blocking=False):
            raise CameraError('Camera processing is busy. Try again.', 503)
        try:
            if path == '/api/camera/background':
                self.remember(session, decode_frame(data))
                return {'ok': True}

            background = self.background(session)
            frame = decode_frame(data)
            if frame.shape != background.shape:
                raise CameraError('Camera dimensions changed. Capture a new empty background.', 409)
            roads = read_roads(headers, frame.shape)
            threshold = integer_header(headers, 'X-Threshold', 255)
            min_area = integer_header(headers, 'X-Min-Area', 20000)
            detections = []
            for road in roads:
                result = count_objects(frame, background, road, threshold, min_area)
                if not result.valid:
                    return {'reason': result.reason}
                detections.append(result)
            return {
                'counts': [result.count for result in detections],
                'boxes': [result.boxes for result in detections],
            }
        finally:
            self.workers.release()

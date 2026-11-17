#!/usr/bin/env python3
"""Mac camera -> model-car counts -> existing ESP32 HTTP API."""
import argparse
import threading
import time
import urllib.parse
import urllib.request
import cv2
import numpy as np
from detector import count_objects, StableCounts

WINDOW = 'Model traffic - iPhone camera on Mac'

class Camera:
    """Drain camera continuously; never intentionally reuse a stale frame."""
    def __init__(self, index):
        self.capture = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
        if not self.capture.isOpened():
            raise RuntimeError('Cannot open camera. Check Continuity Camera, camera permission and --camera index.')
        self.lock = threading.Lock()
        self.frame = None
        self.stamp = 0
        self.sequence = 0
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()
    def _read(self):
        try:
            while not self.closed.is_set():
                ok, frame = self.capture.read()
                if ok and frame is not None:
                    scale = 640 / frame.shape[1]
                    frame = cv2.resize(frame, (640, round(frame.shape[0]*scale)))
                    with self.lock:
                        self.frame = frame
                        self.stamp = time.monotonic()
                        self.sequence += 1
                else:
                    time.sleep(0.1)
        finally:
            self.capture.release()
    def latest(self):
        with self.lock:
            return (None if self.frame is None else self.frame.copy(), self.stamp, self.sequence)
    def close(self):
        self.closed.set()
        self.thread.join(timeout=2)

def post(esp, path, counts=None):
    data = urllib.parse.urlencode({} if counts is None else {'ns':counts[0], 'ew':counts[1]}).encode()
    request = urllib.request.Request(esp.rstrip('/')+path, data=data, method='POST')
    with urllib.request.urlopen(request, timeout=1) as response:
        if response.status != 200:
            raise RuntimeError('ESP32 rejected request')

def overlap(a, b):
    return max(a[0], b[0]) < min(a[0]+a[2], b[0]+b[2]) and max(a[1], b[1]) < min(a[1]+a[3], b[1]+b[3])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', type=int, default=0, help='Camera index; try 0, 1, 2 if the wrong camera appears')
    parser.add_argument('--esp', default='http://192.168.4.1')
    args = parser.parse_args()
    camera = Camera(args.camera)
    background = None
    roads = None
    armed = False
    stable = StableCounts()
    previous_seq = -1
    last_analysis = last_send = 0
    stable_pair = None
    detections = []
    status = 'Preview only. R: select roads; B: capture EMPTY road; S: send; P: stop; Q: quit'
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, 900, 760)
    cv2.createTrackbar('Difference threshold', WINDOW, 35, 100, lambda _: None)
    cv2.createTrackbar('Minimum car area', WINDOW, 120, 2000, lambda _: None)
    settings = None
    try:
        while True:
            frame, stamp, seq = camera.latest()
            now = time.monotonic()
            fresh = frame is not None and now-stamp < 1.5
            if not fresh:
                stable.reset()
                stable_pair = None
                detections = []
                status = 'No fresh camera frames. Sending stopped; check iPhone connection.'
            current_settings = (max(1, cv2.getTrackbarPos('Difference threshold', WINDOW)),
                                max(1, cv2.getTrackbarPos('Minimum car area', WINDOW)))
            if settings != current_settings:
                settings = current_settings
                stable.reset()
                stable_pair = None
            if fresh and seq != previous_seq and now-last_analysis >= 0.25:
                previous_seq, last_analysis = seq, now
                if background is not None and roads:
                    detections = [count_objects(frame, background, roi, *settings) for roi in roads]
                    pair = tuple(d.count for d in detections) if all(d.valid for d in detections) else None
                    stable_pair = stable.update(pair)
                    if pair is None:
                        status = next(d.reason for d in detections if not d.valid)
                    elif stable_pair is None:
                        status = 'Waiting for 3 matching counts; keep hands outside roads'
                    elif not armed:
                        status = 'Counts ready. S: start sending to ESP32'
                    if armed and stable_pair is not None and now-last_send >= 1:
                        last_send = now
                        try:
                            post(args.esp, '/api/counts', stable_pair)
                            status = 'ESP32 accepted A=%d B=%d (not an LED acknowledgement)' % stable_pair
                        except Exception as error:
                            status = 'Send failed: '+str(error)
            display = frame.copy() if frame is not None else np.zeros((480, 640, 3), np.uint8)
            if roads:
                for i, (x, y, w, h) in enumerate(roads):
                    color = (0, 220, 255) if i == 0 else (255, 200, 0)
                    cv2.rectangle(display, (x,y), (x+w,y+h), color, 2)
                    count = detections[i].count if len(detections)==2 and detections[i].valid else '?'
                    cv2.putText(display, '%s: %s' % ('AB'[i], count), (x+4,y+24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                for d in detections:
                    for x,y,w,h in d.boxes:
                        cv2.rectangle(display, (x,y), (x+w,y+h), (0,255,0), 1)
            panel = np.zeros((135, display.shape[1], 3), np.uint8)
            lines = ['SENDING' if armed else 'PREVIEW / NOT SENDING', status[:86],
                     'R roads | B empty background | S send | P pause | Q quit',
                     'Separated toy cars only. Keep camera and lighting fixed.']
            for i, text in enumerate(lines):
                cv2.putText(panel, text, (8,25+i*30), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (255,255,255), 1)
            cv2.imshow(WINDOW, np.vstack([display,panel]))
            key = cv2.waitKey(20) & 0xff
            if key in (ord('q'),27) or cv2.getWindowProperty(WINDOW,cv2.WND_PROP_VISIBLE)<1:
                break
            if key == ord('p'):
                armed = False
                status = 'Paused; requesting fixed timing'
                try: post(args.esp, '/api/auto')
                except Exception: status = 'Paused. Uno falls back after old counts expire.'
            if key == ord('r') and fresh:
                armed = False
                background = None
                stable.reset()
                stable_pair = None
                detections = []
                # No background sends occur during selection; old counts expire on Uno.
                selected = []
                for name in ('A','B'):
                    title = 'Select road '+name+' waiting area - drag then ENTER; C cancels'
                    roi = tuple(map(int,cv2.selectROI(title,frame,False,False)))
                    cv2.destroyWindow(title)
                    if roi[2]<10 or roi[3]<10: break
                    selected.append(roi)
                roads = selected if len(selected)==2 and not overlap(*selected) else None
                status = 'Clear ALL cars and hands, wait for exposure, then B' if roads else 'Select two non-overlapping road areas with R'
            if key == ord('b') and fresh and roads:
                armed = False
                background = frame.copy()
                stable.reset()
                stable_pair = None
                status = 'Empty background captured. Add cars separately; S sends after stable counts.'
            if key == ord('s'):
                if fresh and background is not None and roads and stable_pair is not None:
                    armed = True
                    status = 'Sending enabled'
                else:
                    status = 'First select roads, capture EMPTY background and wait for stable counts.'
    finally:
        camera.close()
        cv2.destroyAllWindows()
        try: post(args.esp, '/api/auto')
        except Exception: pass

if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt: pass

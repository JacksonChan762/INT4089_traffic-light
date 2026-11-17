"""Counts separated foreground objects against a fixed empty-road background.
This is a model-road experiment, not a trained car-classification model.
"""
from dataclasses import dataclass
import cv2
import numpy as np

@dataclass
class Detection:
    count: int
    boxes: list
    valid: bool
    reason: str = ''

def count_objects(frame, background, roi, threshold=35, min_area=120, max_fraction=0.35):
    x, y, w, h = map(int, roi)
    if frame.shape != background.shape or w < 10 or h < 10:
        return Detection(0, [], False, 'Invalid frame or road area')
    if x < 0 or y < 0 or x+w > frame.shape[1] or y+h > frame.shape[0]:
        return Detection(0, [], False, 'Road area outside image')
    current = cv2.GaussianBlur(frame[y:y+h, x:x+w], (5, 5), 0)
    empty = cv2.GaussianBlur(background[y:y+h, x:x+w], (5, 5), 0)
    # Max channel difference preserves sensitivity to coloured toys.
    mask = (cv2.absdiff(current, empty).max(axis=2) > threshold).astype('uint8') * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    if np.count_nonzero(mask) > w*h*0.55:
        return Detection(0, [], False, 'Scene changed: clear hands/check lighting/recalibrate')
    total, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    boxes = []
    for i in range(1, total):
        bx, by, bw, bh, area = stats[i]
        if area < min_area:
            continue
        if area > w*h*max_fraction:
            return Detection(0, [], False, 'Large object or touching cars; separate cars')
        boxes.append((int(x+bx), int(y+by), int(bw), int(bh)))
    if len(boxes) > 99:
        return Detection(0, [], False, 'Too many objects')
    return Detection(len(boxes), boxes, True)

class StableCounts:
    def __init__(self, required=3):
        self.required = required
        self.reset()
    def reset(self):
        self.last = None
        self.repeats = 0
    def update(self, counts):
        if counts is None:
            self.reset()
            return None
        if counts == self.last:
            self.repeats += 1
        else:
            self.last, self.repeats = counts, 1
        return counts if self.repeats >= self.required else None

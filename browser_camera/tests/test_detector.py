import unittest

import numpy as np

from browser_camera.detector import count_objects


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.empty = np.zeros((180, 320, 3), dtype=np.uint8)
        self.road_a = (0, 0, 160, 180)

    def test_empty(self):
        detection = count_objects(self.empty, self.empty, self.road_a)
        self.assertTrue(detection.valid)
        self.assertEqual(detection.count, 0)

    def test_stationary_objects_in_each_road(self):
        frame = self.empty.copy()
        frame[20:40, 20:40] = (50, 100, 220)
        frame[90:110, 20:40] = (100, 220, 50)
        frame[30:50, 230:250] = (220, 100, 50)
        road_b = (160, 0, 160, 180)
        self.assertEqual(count_objects(frame, self.empty, self.road_a).count, 2)
        self.assertEqual(count_objects(frame, self.empty, road_b).count, 1)

    def test_noise_filtered(self):
        frame = self.empty.copy()
        frame[30, 30] = 255
        self.assertEqual(count_objects(frame, self.empty, self.road_a).count, 0)

    def test_large_scene_change_rejected(self):
        frame = np.full_like(self.empty, 200)
        self.assertFalse(count_objects(frame, self.empty, self.road_a).valid)

    def test_bad_geometry(self):
        self.assertFalse(count_objects(self.empty, self.empty, (310, 0, 100, 100)).valid)
        self.assertFalse(count_objects(self.empty[:10], self.empty, self.road_a).valid)

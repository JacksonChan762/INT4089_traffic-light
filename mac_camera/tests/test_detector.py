import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import numpy as np
from detector import count_objects, StableCounts
from camera_control import post, overlap

class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.empty = np.zeros((180,320,3), dtype=np.uint8)
        self.roi = (0,0,160,180)
    def test_empty(self):
        d=count_objects(self.empty,self.empty,self.roi)
        self.assertTrue(d.valid)
        self.assertEqual(d.count,0)
    def test_stationary_separate_cars_and_other_lane(self):
        frame=self.empty.copy()
        frame[20:40,20:40]=(50,100,220)
        frame[90:110,20:40]=(100,220,50)
        frame[30:50,230:250]=(220,100,50)
        for _ in range(5):
            self.assertEqual(count_objects(frame,self.empty,self.roi).count,2)
            self.assertEqual(count_objects(frame,self.empty,(160,0,160,180)).count,1)
    def test_noise_filtered(self):
        frame=self.empty.copy()
        frame[30,30]=255
        self.assertEqual(count_objects(frame,self.empty,self.roi).count,0)
    def test_large_scene_change_rejected(self):
        self.assertFalse(count_objects(np.full_like(self.empty,200),self.empty,self.roi).valid)
    def test_bad_geometry(self):
        self.assertFalse(count_objects(self.empty,self.empty,(310,0,100,100)).valid)
        self.assertFalse(count_objects(self.empty[:10],self.empty,self.roi).valid)
    def test_stability_and_invalid_reset(self):
        s=StableCounts()
        self.assertIsNone(s.update((2,1)))
        self.assertIsNone(s.update((2,1)))
        self.assertEqual(s.update((2,1)),(2,1))
        self.assertIsNone(s.update(None))
        self.assertIsNone(s.update((2,1)))
        self.assertIsNone(s.update((3,1)))
    def test_nonoverlapping_roads(self):
        self.assertFalse(overlap((0,0,10,10),(10,0,10,10)))
        self.assertTrue(overlap((0,0,10,10),(9,0,10,10)))
    def test_esp_protocol(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append((self.path,self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200);self.end_headers();self.wfile.write(b'Accepted')
            def log_message(self,*args): pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base='http://127.0.0.1:%d'%server.server_port
            post(base,'/api/counts',(8,3));post(base,'/api/auto')
            self.assertEqual(requests,[('/api/counts',b'ns=8&ew=3'),('/api/auto',b'')])
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__': unittest.main()

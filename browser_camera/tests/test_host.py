import http.client
import json
import queue
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np


class MockGateway(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        self.server.commands.put((self.path, body))
        self.send_response(200)
        self.end_headers()


class BrowserHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gateway = ThreadingHTTPServer(('127.0.0.1', 0), MockGateway)
        gateway.commands = queue.Queue()
        cls.gateway = gateway
        cls.addClassCleanup(gateway.server_close)
        threading.Thread(target=gateway.serve_forever, daemon=True).start()
        cls.addClassCleanup(gateway.shutdown)
        cls.host = subprocess.Popen(
            [sys.executable, '-m', 'browser_camera.server', '--port', '0',
             '--esp', f'http://127.0.0.1:{gateway.server_port}'],
            stdout=subprocess.PIPE, text=True,
        )
        cls.addClassCleanup(cls.stop_host)
        startup = cls.host.stdout.readline()
        if not startup.startswith('Open http://127.0.0.1:'):
            raise RuntimeError(f'Camera host failed to start: {startup!r}')
        cls.port = int(startup.split('http://127.0.0.1:', 1)[-1].split(' ', 1)[0])
        cls.origin = f'http://127.0.0.1:{cls.port}'

    @classmethod
    def stop_host(cls):
        cls.host.terminate()
        try:
            cls.host.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.host.kill()
            cls.host.wait()
        cls.host.stdout.close()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        self.addCleanup(connection.close)
        connection.request(method, path, body=body, headers={'Origin': self.origin, **(headers or {})})
        with connection.getresponse() as response:
            return response.status, response.read()

    def test_serves_camera_dashboard(self):
        for path in ('/', '/app.js', '/styles.css'):
            with self.subTest(path=path):
                code, body = self.request('GET', path)
                self.assertEqual(code, 200)
                self.assertTrue(body)

    def test_counts_objects_and_forwards_only_control_commands(self):
        background = np.full((180, 320, 3), 35, dtype=np.uint8)
        objects = background.copy()
        for center in ((55, 55), (95, 110), (235, 70)):
            cv2.circle(objects, center, 12, (230, 230, 230), -1)
        camera_headers = {'Content-Type': 'image/jpeg', 'X-Camera-Session': 'a' * 32}
        road_headers = {**camera_headers, 'X-Road-A': '20,20,125,140', 'X-Road-B': '175,20,125,140',
                        'X-Threshold': '35', 'X-Min-Area': '120'}

        code, body = self.request('POST', '/api/camera/background',
                                  cv2.imencode('.jpg', background)[1].tobytes(), camera_headers)
        self.assertEqual((code, json.loads(body)), (200, {'ok': True}))
        frame = cv2.imencode('.jpg', objects)[1].tobytes()
        code, body = self.request('POST', '/api/camera/analyze', frame, road_headers)
        self.assertEqual(code, 200)
        detection = json.loads(body)
        self.assertEqual(detection['counts'], [2, 1])
        self.assertEqual([len(lane) for lane in detection['boxes']], [2, 1])
        self.assertTrue(self.gateway.commands.empty())

        code, _ = self.request('POST', '/api/counts', b'ns=2&ew=1',
                               {'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(code, 200)
        self.assertEqual(self.gateway.commands.get_nowait(), ('/api/counts', b'ns=2&ew=1'))
        code, _ = self.request('POST', '/api/auto', b'')
        self.assertEqual(code, 200)
        self.assertEqual(self.gateway.commands.get_nowait(), ('/api/auto', b''))


if __name__ == '__main__':
    unittest.main()

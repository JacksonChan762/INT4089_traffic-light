import http.client
import json
import queue
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import cv2
import numpy as np

from browser_camera.discovery import Gateway
from browser_camera.packaging import launch
from browser_camera.server import make_server


class MockGateway(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/api/gateway':
            self.send_error(404)
            return
        body = json.dumps({'id': self.server.device_id, 'service': 'int4089-traffic-light',
                           'version': 1}).encode('utf-8')
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        self.server.commands.put((self.path, body))
        self.send_response(200)
        self.end_headers()


class BrowserHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('http.server.socket.getfqdn', return_value='127.0.0.1'):
            gateway = ThreadingHTTPServer(('127.0.0.1', 0), MockGateway)
        gateway.commands = queue.Queue()
        gateway.device_id = '001122aabbcc'
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

    @classmethod
    def stop_host(cls):
        cls.host.terminate()
        try:
            cls.host.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.host.kill()
            cls.host.wait()
        cls.host.stdout.close()

    def request(self, method, path, body=None, headers=None, port=None):
        port = self.port if port is None else port
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        self.addCleanup(connection.close)
        connection.request(method, path, body=body, headers={'Origin': f'http://127.0.0.1:{port}', **(headers or {})})
        with connection.getresponse() as response:
            return response.status, response.read()

    def test_serves_camera_dashboard(self):
        for path in ('/', '/app.js', '/styles.css', '/traffic-test'):
            with self.subTest(path=path):
                code, body = self.request('GET', path)
                self.assertEqual(code, 200)
                self.assertTrue(body)

    def test_camera_dashboard_is_in_english(self):
        code, body = self.request('GET', '/')
        self.assertEqual(code, 200)
        self.assertIn(b'<html lang="en">', body)
        self.assertIn(b'Traffic Light Dashboard', body)

    def test_reports_manual_gateway(self):
        code, body = self.request('GET', '/api/gateways')
        self.assertEqual((code, json.loads(body)),
                         (200, {'mode': 'manual', 'address': '127.0.0.1', 'gateways': []}))

    def test_automatic_commands_require_the_paired_device_identity(self):
        device_id = self.gateway.device_id
        other_id = '112233aabbcc'
        with patch('browser_camera.server.GatewayDiscovery') as discovery_class:
            discovery = discovery_class.return_value
            discovery.get.side_effect = lambda identifier: Gateway(
                identifier, 'Test ESP32', '127.0.0.1', self.gateway.server_port)
            with make_server('127.0.0.1', 0, None) as host:
                threading.Thread(target=host.serve_forever, daemon=True).start()
                try:
                    port = host.server_port
                    code, _ = self.request('POST', '/api/auto', b'', port=port)
                    self.assertEqual(code, 409)
                    code, _ = self.request('POST', '/api/auto', b'', {'X-Gateway-ID': other_id}, port=port)
                    self.assertEqual(code, 503)
                    self.assertTrue(self.gateway.commands.empty())
                    code, _ = self.request('POST', '/api/auto', b'', {'X-Gateway-ID': device_id}, port=port)
                    self.assertEqual(code, 200)
                    self.assertEqual(self.gateway.commands.get_nowait(), ('/api/auto', b''))
                finally:
                    host.shutdown()

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


class LauncherTests(unittest.TestCase):
    def test_computer_camera_uses_discovery_in_one_prompt(self):
        with (
            patch.object(sys, 'argv', ['launch.py']),
            patch('builtins.input', return_value='') as prompt,
            patch.object(launch, 'run_server') as run_server,
        ):
            launch.start()
        prompt.assert_called_once()
        run_server.assert_called_once_with(['--open-browser'])

    def test_phone_camera_uses_discovery_with_https(self):
        with (
            patch.object(sys, 'argv', ['launch.py']),
            patch('builtins.input', side_effect=['192.168.1.10', '', '']),
            patch.object(launch, 'run_server') as run_server,
        ):
            launch.start()
        run_server.assert_called_once_with(['--bind', '192.168.1.10', '--cert', 'traffic-cert.pem',
                                            '--key', 'traffic-key.pem'])

    def test_usb_setup_opens_dashboard_with_discovery(self):
        with (
            patch.object(sys, 'argv', ['launch.py']),
            patch('builtins.input', return_value='W'),
            patch.object(launch, 'setup_wifi', return_value=True) as setup,
            patch.object(launch, 'run_server') as run_server,
        ):
            launch.start()
        setup.assert_called_once_with()
        run_server.assert_called_once_with(['--open-browser'])

    def test_manual_arguments_bypass_launcher_prompt(self):
        with (
            patch.object(sys, 'argv', ['launch.py', '--esp', 'http://192.168.1.20']),
            patch('builtins.input') as prompt,
            patch.object(launch, 'run_server') as run_server,
        ):
            launch.start()
        prompt.assert_not_called()
        run_server.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()

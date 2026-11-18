"""Serve the browser dashboard and forward commands to the ESP32."""

import argparse
import http.client
import ipaddress
import json
import re
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlsplit
import webbrowser

from .camera import CAMERA_ROUTES, MAX_JPEG_BYTES, CameraAnalysis, CameraError
from .discovery import GatewayDiscovery, gateway_matches


ASSETS = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
    '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
}
ASSET_DIRECTORY = Path(__file__).resolve().parent
GATEWAY_ROUTES = ('/api/counts', '/api/auto')


def gateway_address(url):
    try:
        address = urlsplit(url)
        host = str(ipaddress.IPv4Address(address.hostname))
        port = 80 if address.port is None else address.port
        if (address.scheme != 'http' or not port or address.username is not None or
                address.path not in ('', '/') or address.query or address.fragment):
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError('Use the ESP32 HTTP IPv4 URL, e.g. http://192.168.137.30') from None
    return host, port


def count_body(raw):
    fields = parse_qs(raw.decode('ascii'), strict_parsing=True,
                      keep_blank_values=True, max_num_fields=2,
                      encoding='ascii', errors='strict')
    if fields.keys() != {'ns', 'ew'} or any(
        len(values) != 1 or not re.fullmatch(r'[0-9]{1,2}', values[0])
        for values in fields.values()
    ):
        raise ValueError
    return urlencode({field: fields[field][0] for field in ('ns', 'ew')}).encode('ascii')


class CameraHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def log_request(self, code='-', size='-'):
        if self.path == '/api/gateways' and str(code) == '200':
            return
        if self.path not in CAMERA_ROUTES or str(code) not in ('200', '409'):
            super().log_request(code, size)

    def reply(self, code, body, content_type='text/plain; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Permissions-Policy', 'camera=(self), microphone=()')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; media-src 'self' blob:; object-src 'none'; "
                         "base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def request_origin(self):
        scheme = self.server.scheme
        host, port = self.server.server_address
        names = (host, 'localhost') if host == '127.0.0.1' else (host,)
        suffix = '' if (scheme, port) in (('http', 80), ('https', 443)) else f':{port}'
        hosts = self.headers.get_all('Host', [])
        if len(hosts) == 1 and hosts[0] in {name + suffix for name in names}:
            return f'{scheme}://{hosts[0]}'
        return None

    def do_GET(self):
        if self.request_origin() is None:
            self.reply(400, b'Unexpected host')
            return
        if self.path == '/api/gateways':
            body = json.dumps(self.server.gateway_status()).encode('utf-8')
            self.reply(200, body, 'application/json; charset=utf-8')
            return
        if self.path not in ASSETS:
            self.reply(404, b'Not found')
            return
        name, content_type = ASSETS[self.path]
        try:
            body = (ASSET_DIRECTORY / name).read_bytes()
        except OSError:
            self.reply(500, b'Browser camera asset is missing')
            return
        self.reply(200, body, content_type)

    def do_POST(self):
        camera_route = self.path in CAMERA_ROUTES
        if not camera_route and self.path not in GATEWAY_ROUTES:
            self.reply(404, b'Not found')
            return
        origin = self.request_origin()
        if origin is None or self.headers.get_all('Origin', []) != [origin]:
            self.reply(403, b'Open the browser dashboard to send commands')
            return
        lengths = self.headers.get_all('Content-Length', ['0'])
        if (self.headers.get('Transfer-Encoding') is not None or len(lengths) != 1 or
                not re.fullmatch(r'[0-9]{1,6}', lengths[0])):
            self.reply(400, b'Invalid body length')
            return
        length = int(lengths[0])
        if length > (MAX_JPEG_BYTES if camera_route else 64):
            self.reply(413, b'Request body is too large')
            return
        body = self.rfile.read(length)
        if len(body) != length:
            self.reply(400, b'Incomplete request')
            return
        if camera_route:
            self.camera_post(body)
        else:
            self.gateway_post(body)

    def camera_post(self, body):
        try:
            result = self.server.camera.process(self.path, self.headers, body)
            code = 200
        except CameraError as error:
            result = {'reason': str(error)}
            code = error.status
        self.reply(code, json.dumps(result).encode('utf-8'), 'application/json; charset=utf-8')

    def gateway_post(self, body):
        if self.path == '/api/counts':
            if self.headers.get_content_type() != 'application/x-www-form-urlencoded':
                self.reply(415, b'Expected URL-encoded counts')
                return
            try:
                body = count_body(body)
            except ValueError:
                self.reply(400, b'ns and ew must be integers from 0 to 99')
                return
        elif body:
            self.reply(400, b'Fixed timing takes no body')
            return

        gateway = self.server.gateway
        if self.server.discovery is not None:
            identifiers = self.headers.get_all('X-Gateway-ID', [])
            if len(identifiers) != 1 or not identifiers[0]:
                self.reply(409, b'Choose an ESP32 on the dashboard first.')
                return
            selected = self.server.discovery.get(identifiers[0])
            if selected is None or not gateway_matches(selected):
                self.reply(503, b'The paired ESP32 is offline. Waiting for it to reconnect.')
                return
            gateway = selected.endpoint

        connection = http.client.HTTPConnection(*gateway, timeout=2)
        try:
            connection.request('POST', self.path, body, {
                'Content-Type': 'application/x-www-form-urlencoded',
            })
            accepted = connection.getresponse().status == 200
        except (OSError, http.client.HTTPException):
            self.reply(502, b'Cannot reach ESP32. Check its address and Wi-Fi connection.')
            return
        finally:
            connection.close()
        if accepted:
            self.reply(200, b'Accepted by ESP32')
        else:
            self.reply(502, b'ESP32 rejected the command')


class CameraServer(ThreadingHTTPServer):
    def __init__(self, bind, port, gateway, tls=None):
        self.scheme = 'https' if tls else 'http'
        self.gateway = gateway
        self.tls = tls
        self.camera = CameraAnalysis()
        self.discovery = None
        super().__init__((bind, port), CameraHandler)
        if gateway is None:
            self.discovery = GatewayDiscovery()

    def server_bind(self):
        # The dashboard binds a numeric IPv4 address and needs no reverse DNS lookup.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address

    def gateway_status(self):
        if self.discovery is not None:
            return self.discovery.status()
        return {'mode': 'manual', 'address': self.gateway[0], 'gateways': []}

    def server_close(self):
        if self.discovery is not None:
            self.discovery.close()
        super().server_close()

    def get_request(self):
        connection, address = super().get_request()
        if self.tls is None:
            return connection, address
        try:
            return self.tls.wrap_socket(connection, server_side=True, do_handshake_on_connect=False), address
        except OSError:
            connection.close()
            raise

    def service_actions(self):
        self.camera.expire()


def make_server(bind, port, gateway, cert=None, key=None):
    address = ipaddress.IPv4Address(bind)
    if address.is_unspecified or address.is_multicast:
        raise ValueError('Choose a specific IPv4 address assigned to this computer')
    if bool(cert) != bool(key):
        raise ValueError('--cert and --key must be supplied together')
    if not address.is_loopback and not cert:
        raise ValueError('LAN access requires HTTPS. Supply --cert and --key.')
    tls = None
    if cert:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cert, key)
    return CameraServer(str(address), port, gateway, tls)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--esp', type=gateway_address,
                        help='ESP32 HTTP IPv4 URL. With no address, discover gateways on the local network.')
    parser.add_argument('--bind', default='127.0.0.1',
                        help='IPv4 address of this computer to listen on (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--cert', help='PEM certificate and any intermediate certificates')
    parser.add_argument('--key', help='PEM private key for --cert')
    parser.add_argument('--open-browser', action='store_true', help='Open the dashboard in the default browser')
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error('--port must be between 0 and 65535')
    try:
        server = make_server(args.bind, args.port, args.esp, args.cert, args.key)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    with server:
        host, port = server.server_address
        url = f'{server.scheme}://{host}:{port}'
        print(f'Open {url} in your browser. Ctrl+C to stop.', flush=True)
        if args.open_browser:
            Thread(target=webbrowser.open, args=(url,), daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()

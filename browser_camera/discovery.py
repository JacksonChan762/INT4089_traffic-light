"""Discover ESP32 gateways on the computer's local Wi-Fi or LAN."""

from dataclasses import dataclass
import http.client
import ipaddress
import json
import re
from threading import Event, Lock, Thread

import ifaddr
from zeroconf import IPVersion, ServiceBrowser, ServiceListener, Zeroconf


SERVICE_TYPE = '_traffic-light._tcp.local.'
DEVICE_ID = re.compile(rb'[0-9a-f]{12}')
DISCOVERY_INTERVAL = 2


@dataclass(frozen=True)
class Gateway:
    id: str
    name: str
    address: str
    port: int

    @property
    def endpoint(self):
        return self.address, self.port


def ipv4_interfaces():
    return frozenset(ipaddress.IPv4Interface((ip.ip, ip.network_prefix))
                     for adapter in ifaddr.get_adapters() for ip in adapter.ips
                     if isinstance(ip.ip, str) and ip.ip != '0.0.0.0')


def gateway_matches(gateway):
    # Confirm the application and device ID before routing lighting commands.
    connection = http.client.HTTPConnection(*gateway.endpoint, timeout=.65)
    try:
        connection.request('GET', '/api/gateway', headers={'Connection': 'close'})
        response = connection.getresponse()
        if response.status != 200:
            return False
        body = response.read(1025)
        if len(body) > 1024:
            return False
        data = json.loads(body)
        return (isinstance(data, dict) and data.get('id') == gateway.id and
                data.get('service') == 'int4089-traffic-light' and data.get('version') == 1)
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def service_gateway(info, networks):
    if info is None or not info.port or not 1 <= info.port <= 65535:
        return None
    identifier = info.properties.get(b'id')
    if not identifier or not DEVICE_ID.fullmatch(identifier) or info.properties.get(b'v') != b'1':
        return None
    for address in info.parsed_addresses(IPVersion.V4Only):
        ip = ipaddress.IPv4Address(address)
        if ip.is_unspecified or ip.is_multicast or not any(ip in network for network in networks):
            continue
        gateway = Gateway(identifier.decode('ascii'), info.name.removesuffix('.' + SERVICE_TYPE),
                          address, info.port)
        if gateway_matches(gateway):
            return gateway
    return None


class GatewayDiscovery(ServiceListener):
    def __init__(self):
        self._lock = Lock()
        self._services = set()
        self._gateways = {}
        self._state = 'searching'
        self._closed = Event()
        self._thread = Thread(target=self._run, name='esp32-discovery', daemon=True)
        self._thread.start()

    def add_service(self, zeroconf, service_type, name):
        with self._lock:
            self._services.add(name)

    def update_service(self, zeroconf, service_type, name):
        self.add_service(zeroconf, service_type, name)

    def remove_service(self, zeroconf, service_type, name):
        with self._lock:
            self._services.discard(name)
            self._gateways.pop(name, None)

    def status(self):
        with self._lock:
            gateways = {gateway.id: gateway for gateway in self._gateways.values()}
            state = self._state
        return {
            'mode': 'auto',
            'state': state,
            'gateways': [
                {'id': gateway.id, 'name': gateway.name, 'address': gateway.address}
                for gateway in sorted(gateways.values(), key=lambda item: item.id)
            ],
        }

    def get(self, identifier):
        with self._lock:
            return next((gateway for gateway in self._gateways.values()
                         if gateway.id == identifier), None)

    def close(self):
        self._closed.set()
        self._thread.join()

    def _run(self):
        while not self._closed.is_set():
            try:
                interfaces = ipv4_interfaces()
                if interfaces:
                    with Zeroconf(interfaces=sorted({str(entry.ip) for entry in interfaces}),
                                  ip_version=IPVersion.V4Only) as zeroconf:
                        self._browse(zeroconf, interfaces)
                else:
                    self._closed.wait(DISCOVERY_INTERVAL)
            except OSError:
                with self._lock:
                    self._state = 'unavailable'
                self._closed.wait(DISCOVERY_INTERVAL)

    def _browse(self, zeroconf, interfaces):
        networks = {entry.network for entry in interfaces}
        browser = ServiceBrowser(zeroconf, SERVICE_TYPE, self)
        try:
            with self._lock:
                self._state = 'searching'
            while not self._closed.is_set():
                self._refresh(zeroconf, networks)
                if self._closed.wait(DISCOVERY_INTERVAL) or ipv4_interfaces() != interfaces:
                    break
        finally:
            browser.cancel()
            with self._lock:
                self._services.clear()
                self._gateways.clear()

    def _refresh(self, zeroconf, networks):
        with self._lock:
            names = self._services.copy()
        connected = {}
        for name in sorted(names):
            if self._closed.is_set():
                return
            info = zeroconf.get_service_info(SERVICE_TYPE, name, timeout=650)
            gateway = service_gateway(info, networks)
            if gateway is not None:
                connected[name] = gateway
        with self._lock:
            self._gateways = {name: gateway for name, gateway in connected.items()
                              if name in self._services}

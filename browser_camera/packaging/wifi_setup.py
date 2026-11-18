"""Configure the project's ESP32 Wi-Fi settings over USB serial."""

import getpass
import ipaddress
import re
import warnings
from time import monotonic

import serial
from serial.tools import list_ports


SSID_PROMPT = b'Enter the 2.4 GHz Wi-Fi name (SSID), then press Enter.'
PASSWORD_PROMPT = b'Enter the Wi-Fi password (empty for an open network), then press Enter.'
SAVE_ACK = b'Wi-Fi settings saved. Restarting.'
SAVE_ERROR = b'Could not save Wi-Fi settings. Type wifi to retry.'
STATUS_MESSAGES = (
    b"Wi-Fi setup required. Type wifi to configure the computer's network.",
    b'Waiting for Wi-Fi. Check the hotspot/router or type wifi to reconfigure.',
)
STATUS_ADDRESS_PREFIX = b'Gateway on computer Wi-Fi: http://'
SERIAL_LABEL = re.compile(r'usb[- ]?(?:serial|modem)|usb to uart|tty(?:usb|acm)', re.IGNORECASE)


def select_port():
    ports = sorted((port for port in list_ports.comports()
                    if port.vid is not None or SERIAL_LABEL.search(f'{port.device} {port.description or ""}')),
                   key=lambda port: port.device)
    if not ports:
        print('No USB serial port found. Connect the ESP32 with a USB data cable.')
        return None
    if len(ports) == 1:
        return ports[0].device

    print('Select the USB port for the ESP32 gateway:')
    for number, port in enumerate(ports, 1):
        print(f'  {number}. {port.device} ({port.description or "USB serial"})')
    answer = input('Port number (Enter to cancel): ').strip()
    if not answer:
        print('Wi-Fi setup cancelled.')
        return None
    try:
        number = int(answer)
    except ValueError:
        number = 0
    if not 1 <= number <= len(ports):
        print('Choose a USB port number from the list.')
        return None
    return ports[number - 1].device


def is_gateway_status(line):
    if line in STATUS_MESSAGES:
        return True
    if not line.startswith(STATUS_ADDRESS_PREFIX):
        return False
    try:
        ipaddress.IPv4Address(line[len(STATUS_ADDRESS_PREFIX):].decode('ascii'))
    except ValueError:
        return False
    return True


def wait_for_response(connection, matches, seconds=2):
    deadline = monotonic() + seconds
    line = bytearray()
    too_long = False
    while monotonic() < deadline:
        chunk = connection.read_until(size=256)
        if not too_long:
            line.extend(chunk)
            too_long = len(line) > 256
        if chunk.endswith(b'\n'):
            if not too_long:
                response = bytes(line).rstrip(b'\r\n')
                if matches(response):
                    return response
            line.clear()
            too_long = False
    return None


def write_line(connection, line):
    payload = line + b'\n'
    if connection.write(payload) != len(payload):
        raise serial.SerialException('Incomplete serial write')


def gateway_responds(connection):
    # Some drivers briefly reset the board when opening a port.
    for seconds in (0.75, 1.25, 2):
        write_line(connection, b'status')
        if wait_for_response(connection, is_gateway_status, seconds) is not None:
            return True
    return False


def encode_ssid(value):
    try:
        ssid = value.encode('utf-8')
    except UnicodeEncodeError:
        return None
    if 1 <= len(ssid) <= 32 and all(byte >= 32 and byte != 127 for byte in ssid):
        return ssid
    return None


def encode_password(value):
    if (not value or (8 <= len(value) <= 63 and all(' ' <= char <= '~' for char in value)) or
            re.fullmatch('[0-9a-fA-F]{64}', value)):
        return value.encode('ascii')
    return None


def save_settings(connection, ssid, password):
    write_line(connection, b'wifi')
    if wait_for_response(connection, lambda line: line == SSID_PROMPT) is None:
        print('The ESP32 did not request a Wi-Fi name. Reset the board and try again.')
        return False
    write_line(connection, ssid)
    if wait_for_response(connection, lambda line: line == PASSWORD_PROMPT) is None:
        print('The ESP32 did not request a password. Reset the board and try again.')
        return False
    write_line(connection, password)
    saved = wait_for_response(connection, lambda line: line in (SAVE_ACK, SAVE_ERROR), 3)
    if saved == SAVE_ACK:
        print('Wi-Fi settings saved. The ESP32 is restarting and will try to join the network.')
        return True
    if saved == SAVE_ERROR:
        print('The ESP32 could not save the Wi-Fi settings. Try again.')
    else:
        print('The ESP32 did not confirm saving the Wi-Fi settings. Check the USB connection and try again.')
    return False


def setup_wifi():
    """Run the USB Wi-Fi wizard, returning whether the ESP32 confirmed saving."""
    try:
        device = select_port()
        if device is None:
            return False
        connection = serial.Serial(baudrate=115200, timeout=0.1, write_timeout=1)
        connection.dtr = False
        connection.rts = False
        connection.port = device
        with connection:
            connection.reset_input_buffer()
            if not gateway_responds(connection):
                print('No response from the INT4089 ESP32 firmware. Check the selected port and gateway firmware.')
                return False
            ssid = encode_ssid(input('2.4 GHz Wi-Fi name (SSID): '))
            if ssid is None:
                print('Enter a Wi-Fi name of 1–32 UTF-8 bytes without control characters.')
                return False
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                password = encode_password(getpass.getpass('Wi-Fi password (Enter for an open network): '))
            if password is None:
                print('Use an 8–63 character ASCII password or a 64-digit hexadecimal key.')
                return False
            return save_settings(connection, ssid, password)
    except (EOFError, KeyboardInterrupt):
        print('Wi-Fi setup cancelled.')
    except getpass.GetPassWarning:
        print('Open the launcher in a terminal that supports hidden password input and try again.')
    except (serial.SerialException, OSError):
        print('Could not access the ESP32 over USB. Check the cable and close any serial monitor, then try again.')
    return False

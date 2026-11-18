import io
import unittest
import warnings
from collections import deque
from contextlib import redirect_stdout
from itertools import count
from types import SimpleNamespace
from unittest.mock import patch

from browser_camera.packaging import wifi_setup


NETWORK_NAME = '模型路口'
PASSWORD = 'fixture-password-1'


def serial_port(device='/dev/ttyUSB0', vid=None, description='USB Serial'):
    return SimpleNamespace(device=device, vid=vid, description=description)


class SerialFixture:
    def __init__(self):
        self.port = None
        self.dtr = self.rts = True
        self.opened = None
        self.closed = False
        self.writes = []
        self.incoming = deque()
        self.replies = {
            b'status\n': [b'Boot chatter\r\n', b'Gateway on computer Wi-Fi: ', b'http://192.168.0.5\r\n'],
            b'wifi\n': [wifi_setup.SSID_PROMPT + b'\r\n'],
            NETWORK_NAME.encode('utf-8') + b'\n': [wifi_setup.PASSWORD_PROMPT + b'\r\n'],
            PASSWORD.encode('ascii') + b'\n': [wifi_setup.SAVE_ACK + b'\r\n'],
        }

    def __enter__(self):
        self.opened = self.port, self.dtr, self.rts
        return self

    def __exit__(self, *args):
        self.closed = True

    def reset_input_buffer(self):
        self.incoming.clear()

    def write(self, data):
        self.writes.append(data)
        self.incoming.extend(self.replies.get(data, []))
        return len(data)

    def read_until(self, *, size):
        return self.incoming.popleft() if self.incoming else b''


class WifiSetupTests(unittest.TestCase):
    def setUp(self):
        self.link = SerialFixture()
        self.serial = self.enterContext(patch.object(wifi_setup.serial, 'Serial', return_value=self.link))
        self.ports = self.enterContext(patch.object(wifi_setup.list_ports, 'comports', return_value=[serial_port()]))
        self.answer = self.enterContext(patch('builtins.input', return_value=NETWORK_NAME))
        self.secret = self.enterContext(patch.object(wifi_setup.getpass, 'getpass', return_value=PASSWORD))
        self.enterContext(patch.object(wifi_setup, 'monotonic', side_effect=count(step=0.1).__next__))
        self.output = io.StringIO()
        self.enterContext(redirect_stdout(self.output))

    def test_saves_only_after_gateway_status_and_prompts(self):
        self.assertTrue(wifi_setup.setup_wifi())
        self.serial.assert_called_once_with(baudrate=115200, timeout=0.1, write_timeout=1)
        self.assertEqual(self.link.opened, ('/dev/ttyUSB0', False, False))
        self.assertTrue(self.link.closed)
        self.assertEqual(self.link.writes, [b'status\n', b'wifi\n', NETWORK_NAME.encode('utf-8') + b'\n',
                                            PASSWORD.encode('ascii') + b'\n'])
        self.assertIn('settings saved', self.output.getvalue())
        self.assertNotIn(PASSWORD, self.output.getvalue())

    def test_prompts_for_multiple_usb_ports_and_ignores_bluetooth(self):
        self.ports.return_value = [serial_port('COM5', 123, 'Bridge'), serial_port('COM2', None, 'USB-SERIAL'),
                                   serial_port('COM3', None, 'Bluetooth')]
        self.answer.side_effect = ['2', NETWORK_NAME]
        self.assertTrue(wifi_setup.setup_wifi())
        self.assertEqual(self.link.opened, ('COM5', False, False))
        self.assertNotIn('COM3', self.output.getvalue())

    def test_no_eligible_port_does_not_open_any_port(self):
        self.ports.return_value = [serial_port('/dev/cu.Bluetooth-Incoming-Port', None, 'Bluetooth')]
        self.assertFalse(wifi_setup.setup_wifi())
        self.serial.assert_not_called()
        self.assertIn('No USB serial port', self.output.getvalue())

    def test_wrong_board_receives_only_status_probes(self):
        self.link.replies[b'status\n'] = [b'Arduino UNO\r\n', wifi_setup.SSID_PROMPT + b'\r\n',
                                        b'Gateway on computer Wi-Fi: http://999.1.2.3\r\n']
        self.assertFalse(wifi_setup.setup_wifi())
        self.assertEqual(self.link.writes, [b'status\n'] * 3)
        self.answer.assert_not_called()
        self.secret.assert_not_called()
        self.assertTrue(self.link.closed)
        self.assertIn('No response from the INT4089 ESP32 firmware', self.output.getvalue())

    def test_missing_ssid_prompt_prevents_sending_credentials(self):
        self.link.replies[b'wifi\n'] = [b'Unknown command\r\n']
        self.assertFalse(wifi_setup.setup_wifi())
        self.assertEqual(self.link.writes, [b'status\n', b'wifi\n'])

    def test_missing_password_prompt_prevents_sending_password(self):
        ssid = NETWORK_NAME.encode('utf-8') + b'\n'
        self.link.replies[ssid] = []
        self.assertFalse(wifi_setup.setup_wifi())
        self.assertEqual(self.link.writes, [b'status\n', b'wifi\n', ssid])

    def test_password_echo_warning_cancels_before_entering_wifi_setup(self):
        def unsafe_getpass(*args):
            warnings.warn('fixture echo warning', wifi_setup.getpass.GetPassWarning)
            self.fail('Password echo warning did not interrupt the prompt')

        self.secret.side_effect = unsafe_getpass
        self.assertFalse(wifi_setup.setup_wifi())
        self.assertEqual(self.link.writes, [b'status\n'])
        self.assertIn('terminal that supports hidden password input', self.output.getvalue())

    def test_firmware_save_failure_is_reported(self):
        self.link.replies[PASSWORD.encode('ascii') + b'\n'] = [wifi_setup.SAVE_ERROR + b'\r\n']
        self.assertFalse(wifi_setup.setup_wifi())
        self.assertIn('could not save', self.output.getvalue())
        self.assertNotIn(PASSWORD, self.output.getvalue())

    def test_validates_utf8_ssid_bytes_and_wpa_keys(self):
        self.assertEqual(wifi_setup.encode_ssid('車' * 10 + 'az'), ('車' * 10 + 'az').encode('utf-8'))
        self.assertIsNone(wifi_setup.encode_ssid('車' * 11))
        self.assertIsNone(wifi_setup.encode_ssid('line\nbreak'))
        self.assertIsNone(wifi_setup.encode_ssid('has\x7fdelete'))
        self.assertEqual(wifi_setup.encode_password(''), b'')
        self.assertEqual(wifi_setup.encode_password('F0' * 32), b'F0' * 32)
        self.assertIsNone(wifi_setup.encode_password('FC' * 31 + 'ZZ'))
        self.assertIsNone(wifi_setup.encode_password('1234567'))
        self.assertIsNone(wifi_setup.encode_password('password車'))


if __name__ == '__main__':
    unittest.main()

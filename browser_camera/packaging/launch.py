"""Start the packaged browser host."""

import argparse
import sys

from browser_camera.server import gateway_address, main as run_server


def start():
    if len(sys.argv) > 1:
        run_server()
        return
    try:
        while True:
            address = input('ESP32 IPv4 address [192.168.4.1]: ').strip() or '192.168.4.1'
            esp = 'http://' + address
            try:
                gateway_address(esp)
            except argparse.ArgumentTypeError:
                print('Enter an IPv4 address such as 192.168.137.30.')
            else:
                break
        print('Press Enter for the computer camera, or enter the computer LAN IPv4 for phone HTTPS.')
        bind = input('Computer LAN IPv4 []: ').strip()
        arguments = ['--esp', esp]
        if bind:
            arguments += ['--bind', bind]
            for name, default in [('cert', 'traffic-cert.pem'), ('key', 'traffic-key.pem')]:
                path = input(f'HTTPS {name} path [{default}]: ').strip() or default
                arguments += ['--' + name, path]
        else:
            arguments += ['--open-browser']
    except (EOFError, KeyboardInterrupt):
        return
    run_server(arguments)


if __name__ == '__main__':
    start()

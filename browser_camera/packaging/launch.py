"""Start the packaged browser host."""

import sys

from browser_camera.packaging.wifi_setup import setup_wifi


def run_server(arguments=None):
    # OpenCV is only needed after the user has finished USB setup.
    from browser_camera.server import main

    main(arguments)


def start():
    if len(sys.argv) > 1:
        run_server()
        return
    try:
        print('The dashboard will look for ESP32 boards on the same Wi-Fi network.')
        choice = input('Enter: computer camera | W: ESP32 USB Wi-Fi setup | LAN IPv4: phone HTTPS\n> ').strip()
        if choice.lower() == 'w':
            if not setup_wifi():
                return
            arguments = ['--open-browser']
        elif choice:
            arguments = ['--bind', choice]
            for name, default in [('cert', 'traffic-cert.pem'), ('key', 'traffic-key.pem')]:
                path = input(f'HTTPS {name} path [{default}]: ').strip() or default
                arguments += ['--' + name, path]
        else:
            arguments = ['--open-browser']
    except (EOFError, KeyboardInterrupt):
        return
    run_server(arguments)


if __name__ == '__main__':
    start()

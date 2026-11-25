INT4089 Traffic Light Camera

Extract the complete archive before starting. Keep the launcher with the
browser_camera and python folders. The Python runtime and image-processing
libraries are included.

Windows x64
  Open Start.cmd. Windows 11 ARM can run this package in x64 emulation.

macOS
  Use the Apple Silicon package for an Apple chip or the Intel package for an
  Intel processor. Open Start.command, or run ./Start.command in Terminal.

Linux
  Use the x64 or ARM64 package on a glibc-based distribution such as Ubuntu or
  Debian. In a terminal in the extracted folder, run ./start.sh.

ESP32 Wi-Fi setup
  Flash the current ESP32 gateway firmware. From a phone, join the
  TrafficLight-xxxxxx hotspot using the password Traffic4089 and open
  http://192.168.4.1. Enter the router's 2.4 GHz Wi-Fi name and password.
  The ESP32 saves the network after a successful connection and rejoins it
  automatically. For USB setup, connect the ESP32 to the computer, close any
  serial monitor, then type W at the launcher prompt and follow the prompts.

Light timing log
  The dashboard shows the latest completed signal phases and their actual
  durations. Update both boards and connect the two-way UART through a level
  shifter. The ESP32 also shows the log in its own control page.
  https://github.com/JacksonChan762/INT4089_traffic-light#hardware-and-wiring

Computer camera
  Once the ESP32 is set up, press Enter at the launcher prompt to open
  the dashboard on the computer. Keep both devices on the same Wi-Fi router.
  The dashboard discovers ESP32 gateways automatically. If the browser
  did not open, use the URL printed in the terminal. Open the camera from
  the dashboard.

Phone camera
  Connect the phone to the same Wi-Fi router as the computer and ESP32.
  Obtain a trusted HTTPS certificate for the computer's LAN IP. Type the
  computer's LAN IPv4 address into the launcher, then enter the certificate
  and key paths. Open the printed HTTPS URL on the phone and allow camera
  access. The dashboard discovers ESP32 gateways automatically. With mkcert,
  install only its public root CA on the phone so it can trust the HTTPS
  certificate. Keep the private keys on the computer.
  https://github.com/FiloSottile/mkcert#mobile-devices
  https://support.apple.com/en-us/102390

Automatic ESP32 pairing
  Use the current gateway firmware and keep the dashboard open while the
  ESP32 joins the router's network. The dashboard pairs with one board
  automatically. Select an ESP32 from the menu when multiple boards are found.
  If the network blocks multicast DNS, use the --esp option below.

Advanced
  You can also use a USB serial monitor at 115200 baud. Type wifi and
  press Enter, then enter the router's 2.4 GHz Wi-Fi name and password as
  prompted. Type status after the ESP32 restarts to display its IPv4 address.
  Pass --help to the launcher to see the server options. For example, on
  Linux use ./start.sh --esp http://192.168.1.30 --open-browser, substituting
  the ESP32's assigned IPv4 address.
  Press Ctrl+C in the terminal to stop the host.

Windows startup
  If OpenCV reports a missing DLL, see its Windows troubleshooting section.
  https://pypi.org/project/opencv-python-headless/4.10.0.84/#frequently-asked-questions

Runtime redistribution
  This archive includes CPython from Astral's Python Build Standalone.
  The included runtime and dependency folders contain their license files.
  https://github.com/astral-sh/python-build-standalone/releases/tag/20261110

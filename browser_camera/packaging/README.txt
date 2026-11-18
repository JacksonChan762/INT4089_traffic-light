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

Computer camera
  Enter the ESP32's assigned LAN IP. Press Enter at the second prompt to open
  the dashboard on the computer. If the browser did not open automatically,
  use the URL printed in the terminal. Open the camera from the dashboard.

Phone camera
  Connect the phone to the computer's hotspot or shared local network. Obtain
  a trusted HTTPS certificate for the computer's LAN IP. At the second prompt,
  type the computer's LAN IP, then enter the certificate and key paths. Open
  the printed HTTPS URL on the phone and allow camera access. The phone must
  trust the certificate. With mkcert, install only its public root CA on the
  phone. Keep the private keys on the computer.
  https://github.com/FiloSottile/mkcert#mobile-devices
  https://support.apple.com/en-us/102390

ESP32 setup
  The ESP32 needs the project's gateway firmware and must be reachable from
  the computer. Join the TrafficLight-Lab setup network and open
  http://192.168.4.1/wifi to configure its hotspot or router connection.
  The setup page and USB serial monitor show the assigned ESP32 address.

Advanced
  Pass --help to the launcher to see the server options. For example, on
  Linux use ./start.sh --esp http://192.168.137.30 --open-browser.
  Press Ctrl+C in the terminal to stop the host.

Windows startup
  If OpenCV reports a missing DLL, see its Windows troubleshooting section.
  https://pypi.org/project/opencv-python-headless/4.10.0.84/#frequently-asked-questions

Runtime redistribution
  This archive includes CPython from Astral's Python Build Standalone.
  The included runtime and dependency folders contain their license files.
  https://github.com/astral-sh/python-build-standalone/releases/tag/20261110

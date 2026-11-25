# Browser camera and PC processing

**English** · [繁體中文](README.zh-TW.md)

The dashboard runs on a Mac, Linux PC or Windows PC. Open the dashboard on the device whose camera you want to use. A computer browser can select an internal webcam or USB camera. A phone browser can select a built-in camera and sends compressed frames over Wi-Fi to the same dashboard server. The computer uses OpenCV to count cars and sends the counts to the ESP32. The ESP32 forwards the commands to the Uno over UART.

## Join the computer's network

1. Update the ESP32 using the [build and upload instructions](../README.md#build-and-upload). Connect the computer to an existing Wi-Fi router. The router must offer **2.4 GHz Wi-Fi** for the ESP32 and let devices on its local network communicate.
2. Connect the ESP32 by USB and close any open serial monitor. On Windows x64, run the v1.3.1 setup EXE, then open **Traffic Light Camera** from the Start menu. On macOS or Linux, extract the v1.3.1 archive and open `Start.command` or run `./start.sh`, respectively. [Release downloads](../README.md#download-the-browser-camera-app)
3. At the launcher prompt, type `W` and press Enter. Select the ESP32's serial port if more than one port is listed. Enter the router's 2.4 GHz Wi-Fi name (SSID) and password. The password stays hidden as you type, and the launcher sends the credentials to the board over USB.
4. The ESP32 saves the settings and restarts. The launcher opens the computer dashboard and discovers the board when it joins the router. Once configured, press Enter at the launcher prompt to start the computer camera dashboard. For phone camera access, enter the computer's LAN IPv4 address at launch. [Phone camera setup](#use-a-phone-camera-in-the-browser)

### Configure Wi-Fi from the serial monitor

You can also configure the ESP32 with PlatformIO's USB serial monitor.

1. Find the board's port with `pio device list`, then open the serial monitor. Replace `ESP32_PORT` with that port, such as `COM3` on Windows or `/dev/cu.usbserial-XXXX` on macOS.

   ```sh
   pio device monitor -e esp32 --port ESP32_PORT --filter send_on_enter
   ```

2. Type `wifi` and press Enter. Enter the router's 2.4 GHz Wi-Fi name (SSID), then its password when prompted. Press Enter after each value and keep the monitor's local echo disabled. The ESP32 saves the settings, restarts and joins that network.
3. Look for **Gateway on computer Wi-Fi** in the USB serial monitor at **115200 baud**. Type `status` and press Enter to display the address again. Open the ESP32's HTTP URL from the computer to check connectivity, or use it with `--esp` for manual pairing.

## Find and pair an ESP32

The computer running the dashboard discovers ESP32 gateways on its local network using multicast DNS (mDNS). Use the updated gateway firmware and keep the dashboard open while the board joins Wi-Fi. The dashboard pairs with a single detected ESP32. When it lists multiple boards, select the one you want to control from the **Gateway** menu.

The dashboard remembers the chosen device during the session and finds it again if its IP address changes. After a connection loss or selection change, start sending counts again from the dashboard. If the computer asks for permission to access the local network, allow it. For older firmware or a network that blocks multicast, start the dashboard from a terminal with `--esp http://192.168.1.30`, substituting the ESP32's assigned IPv4 address.

## Release packages

Use the setup EXE on Windows x64 and launch **Traffic Light Camera** from the Start menu. On macOS or Linux, extract the whole archive for your processor and open its launcher. Both formats include Python and OpenCV. At the v1.3.1 launcher prompt, type `W` for USB Wi-Fi setup, press Enter for the computer camera, or enter the computer's LAN IPv4 address and provide the trusted certificate and key for a phone camera. Both camera modes discover ESP32 gateways automatically.

Download v1.3.1 for your operating system and processor. [Release downloads](../README.md#download-the-browser-camera-app)

To build the portable packaging files from source, run `python3.12 browser_camera/packaging/build.py` from the project root with Python 3.12 and pip. The archives and SHA-256 checksums appear under `dist/`.

## Install on the computer

Run these commands from the project root with CPython 3.12.

| Computer | Python to install |
| --- | --- |
| Windows | x64 CPython. On Windows 11 ARM, use x64 CPython through [Windows app emulation](https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-x86-emulation). |
| Linux | x86-64 or ARM64 CPython on a glibc-based distribution, such as Ubuntu or Debian. |
| macOS | Apple Silicon or Intel CPython. The supplied OpenCV wheels require macOS 11+ on Apple Silicon or 12+ on Intel. |

The browser host uses OpenCV Headless to process frames on the computer.

**Linux or macOS**

```sh
python3.12 -m venv .venv-browser
.venv-browser/bin/python -m pip install --only-binary=:all: -r browser_camera/requirements.txt
```

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv-browser
.\.venv-browser\Scripts\python.exe -m pip install --only-binary=:all: -r browser_camera/requirements.txt
```

On Windows 11 ARM with both ARM64 and x64 Python installed, invoke the x64 Python executable directly to create the environment. If OpenCV reports a missing DLL on Windows, see the [OpenCV Windows troubleshooting notes](https://pypi.org/project/opencv-python-headless/4.10.0.84/#frequently-asked-questions).

## Use the computer's camera

Start the web dashboard with automatic ESP32 discovery.

```sh
.venv-browser/bin/python -m browser_camera.server
```

On Windows, use `.\.venv-browser\Scripts\python.exe` in place of `.venv-browser/bin/python`. Open **http://127.0.0.1:8000/** on the same computer. Press **Open camera** and grant camera access. Use the **Camera** menu to switch between available cameras after granting access.

## Use a phone camera in the browser

The phone needs to trust the HTTPS certificate for the computer's network address. A browser treats the phone's `localhost` as the phone itself. Use the computer's LAN URL for both the phone camera and the computer camera when running in this mode. [W3C camera API](https://www.w3.org/TR/mediacapture-streams/#navigator-interface-extensions)

1. Connect the phone to the same Wi-Fi router as the computer and ESP32. Find the computer's IPv4 address on that network in the computer's network settings. In these examples the computer is **192.168.1.20**. Its dashboard discovers the ESP32 on the same network.
2. Install [mkcert](https://github.com/FiloSottile/mkcert) on the computer and create a certificate for its IP address. Run the commands from the project root and substitute the computer's actual address.

   ```sh
   mkcert -install
   mkcert -cert-file traffic-cert.pem -key-file traffic-key.pem 192.168.1.20
   mkcert -CAROOT
   ```

3. Copy **rootCA.pem** from the directory printed by `mkcert -CAROOT` to the phone. Keep **rootCA-key.pem** and **traffic-key.pem** on the computer. On Android, install the public root under the system's **CA certificate** option. If the file picker requires a different extension, copy the same public certificate as `traffic-root.crt`. On iPhone, install the public root certificate and enable full trust under **Settings → General → About → Certificate Trust Settings**. [mkcert mobile instructions](https://github.com/FiloSottile/mkcert#mobile-devices) · [Apple certificate trust instructions](https://support.apple.com/en-us/102390)
4. Start the dashboard in HTTPS mode. Use `.\.venv-browser\Scripts\python.exe` on Windows. If the firewall prompts, allow the dashboard on the private network.

   ```sh
   .venv-browser/bin/python -m browser_camera.server --bind 192.168.1.20 --cert traffic-cert.pem --key traffic-key.pem
   ```

5. Open **https://192.168.1.20:8000/** on the phone in Chrome on Android or Safari on iPhone. Press **Open camera**, allow camera access and choose the desired lens. If the computer's address changes, generate a certificate for the new address and update `--bind`.

## Calibrate and send counts

1. Mount the camera so both waiting areas fit in the preview. Keep the lighting and framing steady.
2. Press **Select Road A**, then drag across road A's waiting area. Repeat with **Select Road B**. The rectangles must be separate.
3. Clear both areas and press **Capture empty background**. Put separated model cars back in the areas. The computer compares each frame with the empty scene and displays boxes and per-road counts. If there are false detections, adjust the difference threshold or minimum car area. If the scene moves, capture a new empty background.
4. After three matching counts, press **Start sending camera counts**. Keep the page in the foreground. Send counts from one dashboard or ESP32 control page at a time.
5. Press **Stop sending and restore fixed timing** to pause adaptive timing, or **Close camera** to release the camera. If the camera or connection drops, the Uno uses its fixed cycle once five seconds have elapsed since the last valid counts. Changes take effect when the next green phase starts.

The host keeps the empty background temporarily in memory. Camera frames are processed on the computer and are never forwarded to the ESP32. Move hands and shadows out of the waiting areas. Cars that touch can appear as one object.

You can enter counts under **Manual counts** and select **Apply and keep sending** without opening a camera. If no computer is available, use the [ESP32 fallback manual page](../README.md#try-the-direct-manual-controls).

## Test the camera with cars at traffic lights

1. Select **Open Traffic Light Test Lab (new tab)** on the dashboard. You can also open `browser_camera/traffic_test.html` directly on another device. Put the test page on a display that the camera can see and use **Expand view** before calibrating if you need a larger image.
2. With both roads empty, open the camera on the dashboard and frame both marked waiting areas. Select each area separately, keeping the signal lamps outside both selections. Click **Capture empty background**, then keep the camera and display fixed.
3. Set the car counts for roads A and B and click **Queue cars**. Both lights stay red and the cars remain still. Compare the dashboard readings with the selected counts in this mode.
4. Click **Start signal cycle** to let cars move and use **Speed** to adjust how fast they drive. Click **Hold red** to return to the stationary queues, or **Clear roads** to restore the empty scene for calibration.

The simulator shows the planned **Red**, **Yellow**, and **Green** durations for each road, plus the current phase and its countdown during the cycle. Each green has a base duration of 10 seconds. The road with more cars gets 2 extra seconds per additional car, up to a total of 20 seconds. Each yellow lasts 3 seconds, followed by 2 seconds with both lights red. The simulator sets each green's duration when that phase starts. These times describe the simulation in the browser.

## Test the host on any platform

From the project root, use the browser environment's Python to run the detector and host integration tests.

```sh
.venv-browser/bin/python -m unittest discover -s browser_camera/tests -v
```

On Windows, use `.\.venv-browser\Scripts\python.exe`. The tests launch the host on loopback, upload synthetic JPEG frames, verify two paper balls on road A and one on road B, and check the final requests received by a mock ESP32.

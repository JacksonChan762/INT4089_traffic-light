# Browser camera and PC processing

The dashboard runs on a Mac, Linux PC or Windows PC. Open the dashboard on the device whose camera you want to use. A computer browser can select an internal webcam or USB camera. A phone browser can select a built-in camera and sends compressed frames over Wi-Fi to the same dashboard server. The computer uses OpenCV to count cars and sends the counts to the ESP32. The ESP32 forwards the commands to the Uno over UART.

## Join the computer's network

1. Update the firmware using the [build and upload instructions](../README.md#build-and-upload). On the computer, start a **2.4 GHz** Wi-Fi hotspot with WPA2, or connect the computer to the same local router the ESP32 will join. If the computer cannot start a hotspot while using its current network connection, use a shared router. Avoid guest networks that isolate devices.
2. Temporarily connect a phone or computer to **TrafficLight-Lab** using the password **traffic123** and open **http://192.168.4.1/wifi**. Enter the hotspot or router's Wi-Fi name and password. The ESP32 saves them, restarts and joins the network.
3. Get the ESP32's assigned address from **Gateway on computer Wi-Fi** in the ESP32's USB serial monitor at **115200 baud**. You can also reconnect to **TrafficLight-Lab** and reopen the setup page to see the address. Switch the computer and phone back to the hotspot or shared router for normal use.
4. From the computer, open `http://ESP32_IP/` to verify that the board is reachable. Use that same address with the dashboard's `--esp` option. If the address changes after a restart, use the new address. Choose a hotspot or router subnet other than `192.168.4.0/24`, which is used for ESP32 setup and fallback.

## Portable packages

Use the archive for your operating system and processor. Extract the whole archive and open the supplied launcher. Its bundled Python and OpenCV run on the computer. Enter the ESP32 address when prompted. For a phone camera, enter the computer's LAN address and provide the trusted certificate and key described below. [Package instructions](packaging/README.txt)

To build the five archives from source, run `python3.12 browser_camera/packaging/build.py` from the project root with Python 3.12 and pip. The archives and SHA-256 checksums appear under `dist/`.

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

Start the web dashboard. Replace `192.168.137.30` with the ESP32's assigned address.

```sh
.venv-browser/bin/python -m browser_camera.server --esp http://192.168.137.30
```

On Windows, use `.\.venv-browser\Scripts\python.exe` in place of `.venv-browser/bin/python`. Open **http://127.0.0.1:8000/** on the same computer. Press **開啟相機** and grant camera access. Use the **相機** menu to switch between available cameras after granting access.

## Use a phone camera in the browser

The phone needs to trust the HTTPS certificate for the computer's network address. A browser treats the phone's `localhost` as the phone itself. Use the computer's LAN URL for both the phone camera and the computer camera when running in this mode. [W3C camera API](https://www.w3.org/TR/mediacapture-streams/#navigator-interface-extensions)

1. Connect the phone to the computer's hotspot or shared router. Find the computer's IPv4 address on that network in the network settings. In these examples the computer is **192.168.137.1** and the ESP32 is **192.168.137.30**.
2. Install [mkcert](https://github.com/FiloSottile/mkcert) on the computer and create a certificate for its IP address. Run the commands from the project root and substitute the computer's actual address.

   ```sh
   mkcert -install
   mkcert -cert-file traffic-cert.pem -key-file traffic-key.pem 192.168.137.1
   mkcert -CAROOT
   ```

3. Copy **rootCA.pem** from the directory printed by `mkcert -CAROOT` to the phone. Keep **rootCA-key.pem** and **traffic-key.pem** on the computer. On Android, install the public root under the system's **CA certificate** option. If the file picker requires a different extension, copy the same public certificate as `traffic-root.crt`. On iPhone, install the public root certificate and enable full trust under **Settings → General → About → Certificate Trust Settings**. [mkcert mobile instructions](https://github.com/FiloSottile/mkcert#mobile-devices) · [Apple certificate trust instructions](https://support.apple.com/en-us/102390)
4. Start the dashboard in HTTPS mode. Use `.\.venv-browser\Scripts\python.exe` on Windows. If the firewall prompts, allow the dashboard on the private network.

   ```sh
   .venv-browser/bin/python -m browser_camera.server --bind 192.168.137.1 --esp http://192.168.137.30 --cert traffic-cert.pem --key traffic-key.pem
   ```

5. Open **https://192.168.137.1:8000/** on the phone in Chrome on Android or Safari on iPhone. Press **開啟相機**, allow camera access and choose the desired lens. If the computer's address changes, generate a certificate for the new address and update `--bind`.

## Calibrate and send counts

1. Mount the camera so both waiting areas fit in the preview. Keep the lighting and framing steady.
2. Press **框選 A 道**, then drag across road A's waiting area. Repeat with **框選 B 道**. The rectangles must be separate.
3. Clear both areas and press **擷取空景**. Put separated model cars back in the areas. The computer compares each frame with the empty scene and displays boxes and per-road counts. If there are false detections, adjust the difference threshold or minimum car area. If the scene moves, capture a new empty background.
4. After three matching counts, press **開始傳送相機車量**. Keep the page in the foreground. Send counts from one dashboard or ESP32 control page at a time.
5. Press **停止傳送並恢復固定時間** to pause adaptive timing, or **關閉相機** to release the camera. If the camera or connection drops, the Uno uses its fixed cycle once five seconds have elapsed since the last valid counts. Changes take effect when the next green phase starts.

The host keeps the empty background temporarily in memory. Camera frames are processed on the computer and are never forwarded to the ESP32. Move hands and shadows out of the waiting areas. Cars that touch can appear as one object.

You can use **手動輸入** in the same dashboard without opening a camera. If no computer is available, use the [ESP32 fallback manual page](../README.md#try-the-direct-manual-controls).

## Test the host on any platform

From the project root, use the browser environment's Python to run the detector and host integration tests.

```sh
.venv-browser/bin/python -m unittest discover -s browser_camera/tests -v
```

On Windows, use `.\.venv-browser\Scripts\python.exe`. The tests launch the host on loopback, upload synthetic JPEG frames, verify two paper balls on road A and one on road B, and check the final requests received by a mock ESP32.

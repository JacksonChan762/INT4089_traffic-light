# INT4089 Smart Traffic Light

**English** · [繁體中文](README.zh-TW.md)

This classroom model uses six LEDs to control a crossing between two one-way roads, A and B. An Arduino Uno R3 alternates the lights and runs a fixed cycle on its own. With an ESP32 connected, the Uno can give the road with the longer queue up to 10 extra seconds of green. Enter queue lengths manually, or run the browser dashboard on a computer to count model cars using a computer webcam or a phone camera.

## Download the browser camera app

Choose the package for your operating system and processor from [GitHub Release v1.1.0](https://github.com/JacksonChan762/INT4089_traffic-light/releases/tag/v1.1.0). Download and extract the entire archive before launching it. Python and OpenCV are included.

| Platform | Direct download | How to start |
| --- | --- | --- |
| Windows x64 | [Download ZIP](https://github.com/JacksonChan762/INT4089_traffic-light/releases/download/v1.1.0/TrafficLight-Camera-windows-x64.zip) | Double-click `Start.cmd` in the extracted folder. |
| Linux x64 | [Download tar.gz](https://github.com/JacksonChan762/INT4089_traffic-light/releases/download/v1.1.0/TrafficLight-Camera-linux-x64.tar.gz) | Open a terminal in the extracted folder and run `./start.sh`. |
| Linux ARM64 | [Download tar.gz](https://github.com/JacksonChan762/INT4089_traffic-light/releases/download/v1.1.0/TrafficLight-Camera-linux-arm64.tar.gz) | Open a terminal in the extracted folder and run `./start.sh`. |
| macOS Apple Silicon | [Download tar.gz](https://github.com/JacksonChan762/INT4089_traffic-light/releases/download/v1.1.0/TrafficLight-Camera-macos-apple-silicon.tar.gz) | Open `Start.command` or run `./Start.command` in Terminal from the extracted folder. |
| macOS Intel | [Download tar.gz](https://github.com/JacksonChan762/INT4089_traffic-light/releases/download/v1.1.0/TrafficLight-Camera-macos-intel.tar.gz) | Open `Start.command` or run `./Start.command` in Terminal from the extracted folder. |

Verify your download with [SHA256SUMS.txt](https://github.com/JacksonChan762/INT4089_traffic-light/releases/download/v1.1.0/SHA256SUMS.txt). The v1.1.0 launcher supports USB Wi-Fi setup and automatic ESP32 discovery with the current gateway firmware. [Browser camera guide](browser_camera/README.md)

## Hardware and wiring

Use an Arduino Uno R3, a classic ESP32-WROOM-32 development board with GPIO16 and GPIO17 available, two USB cables, jumper wires, six low-current LEDs (two each of red, yellow and green), and six 1 kΩ resistors. Check the pinout and PlatformIO board setting before using an ESP32-C3, S3, WROVER or ESP32-CAM.

Disconnect power before wiring. For each LED, connect the Uno pin through its own **1 kΩ resistor** to the anode (long leg), then connect the cathode to GND. These connections assume individual low-current LEDs.

| Road | Red LED | Yellow LED | Green LED |
| --- | --- | --- | --- |
| A (north–south) | D2 | D3 | D4 |
| B (east–west) | D5 | D6 | D7 |

| ESP32 | Uno | Purpose |
| --- | --- | --- |
| GPIO17 (TX) | D10 (RX) | Control commands at 9600 baud |
| GND | GND | Common ground |

Power each board through its own USB cable. Keep the boards’ 5 V and 3.3 V rails separate. For one-way control, leave Uno D11 and ESP32 GPIO16 unconnected. A short direct wire from GPIO17 to D10 can be used for initial bench tests. The Uno firmware disables the internal 5 V pull-up on D10.

### Add a UART level shifter for Uno State

Use a non-inverting level shifter with two channels that support 3.3 V and 5 V push-pull UART in opposite directions at the same time. Disconnect USB power from both boards and remove the direct GPIO17-to-D10 jumper before inserting the shifter.

| Source | Destination |
| --- | --- |
| ESP32 **3V3** | Shifter low-voltage supply (`LV` on a module with LV and HV labels) |
| Uno **5V** | Shifter high-voltage supply (`HV` on a module with LV and HV labels) |
| ESP32 GND and Uno GND | Shifter GND, all on the same ground junction |
| ESP32 **GPIO17 TX** | Channel 1 low-voltage input |
| Channel 1 high-voltage output | Uno **D10 RX** |
| Uno **D11 TX** | Channel 2 high-voltage input |
| Channel 2 low-voltage output | ESP32 **GPIO16 RX** |

Check the module’s pinout before applying power. For a module with direction and enable pins, configure channel 1 for 3.3 V to 5 V and channel 2 for 5 V to 3.3 V, then enable both according to the module’s datasheet. The return signal from Uno D11 must pass through the shifter before it reaches ESP32 GPIO16.

## Build and upload

Install PlatformIO Core or the PlatformIO IDE extension for VS Code. The first build needs internet access to download the toolchains. Open the project folder containing `platformio.ini`. It defines separate Arduino firmware builds for the Uno and ESP32.

From the project root, build both environments and list the connected boards:

```sh
pio run -e uno -e esp32
pio device list
```

Upload the Uno firmware first and check that the LEDs cycle on their own. Then upload the gateway firmware to the ESP32. Replace each example port below with the corresponding port from `pio device list`.

```sh
pio run -e uno -t upload --upload-port /dev/cu.usbmodemXXXX
pio run -e esp32 -t upload --upload-port /dev/cu.usbserial-XXXX
```

The Uno firmware is in [arduino_uno](arduino_uno), including the timing logic in [TrafficController.h](arduino_uno/TrafficController.h). The ESP32 joins the same Wi-Fi router as the computer in station mode, serves a manual page on the local network and forwards commands from [esp32_gateway.cpp](esp32_gateway/esp32_gateway.cpp).

Serial port names vary by host. Use the actual COM port on Windows or the actual `/dev/ttyUSB*` or `/dev/ttyACM*` port on Linux.

## Use the browser dashboard

Connect the Mac, Linux PC or Windows PC to an existing Wi-Fi router and configure the ESP32 over USB to join the same router's 2.4 GHz Wi-Fi. Open the dashboard on the computer to use its built-in or USB camera. For an Android phone or iPhone camera, join the phone to the same router and open the computer's HTTPS dashboard. The computer processes the images and sends the counts to the ESP32. The current dashboard discovers gateways on the local network and pairs automatically when it finds one board. [Browser camera setup and calibration guide](browser_camera/README.md)

In the v1.1.0 launcher, connect the ESP32 over USB, close any serial monitor, and type `W` at the prompt to configure Wi-Fi. If the board is already configured, press Enter for the computer camera or enter the computer's LAN IPv4 address for phone access. [USB Wi-Fi setup](browser_camera/README.md#join-the-computers-network)

## Try the direct manual controls

1. Power both boards. Configure the ESP32 over USB to join the router's 2.4 GHz Wi-Fi, and connect the browser device to the same router. [USB Wi-Fi setup](browser_camera/README.md#join-the-computers-network)
2. Open the `http://` address printed by the ESP32's USB serial monitor at 115200 baud.
3. Enter **8** for **Road A** and **3** for **Road B**, then press **Apply and keep sending**. Keep the page in the foreground so it can resend the counts every second. Press the same button again after editing either field.
4. **Planned signal timing** shows the expected red, yellow, and green durations. In this example, the next A green is **20 seconds** and the next B green is **10 seconds**. The ESP32’s send confirmation indicates receipt at the gateway.
5. With both boards running the updated firmware and wired through the level shifter, select **Check Uno state** under **Uno State**. The latest reply shows the current phase, its total duration and the time remaining, along with fresh counts or fixed timing for the next green. The page checks periodically while visible. Select **Stop checking Uno state** to stop. If the state is unavailable, inspect the Uno D11-to-ESP32 GPIO16 return path and the common ground. With one-way wiring you can still check the phase and duration in the Uno’s USB serial monitor at 115200 baud.
6. Press **Restore fixed timing** to return to fixed timing. If you close the page or disconnect, the Uno falls back to fixed timing five seconds after the last count.

## How the timing works

The Uno starts with both roads red for two seconds, then repeats **A green → A yellow → both red → B green → B yellow → both red**. Each yellow lasts three seconds and each all-red interval lasts two seconds.

Each green starts at 10 seconds. The Uno adds two seconds for each extra car waiting on that road compared with the other, up to five extra cars. Equal counts give both roads 10 seconds. The Uno chooses the duration when green begins, so new counts, expired counts and fixed-mode requests take effect at the next green.

## ESP32 HTTP API

The browser dashboard and direct manual page use the same endpoints. Use one sender at a time so its counts stay in effect. Both fields below accept decimal integers from 0 to 99. The field `ns` represents road A and `ew` represents road B.

```http
POST /api/counts
Content-Type: application/x-www-form-urlencoded

ns=8&ew=3
```

The gateway forwards this example to the Uno as `C,8,3\n` over UART. Send `POST /api/auto` to request fixed timing. The corresponding serial command is `A\n`. In both commands, `\n` represents a newline.

Send `GET /api/state` to query the Uno on demand. A successful JSON response includes `available`, `phase`, `duration_ms`, `remaining_ms`, `counts_fresh`, `ns` and `ew`. Phase values 0 through 5 follow the cycle, starting with all red before A green. Counts are eligible to determine the next green duration while `counts_fresh` is true. The endpoint returns HTTP 503 if the Uno does not send a valid reply.

## Verification

Run the controller tests from the project root:

```sh
c++ -std=c++11 -Wall -Wextra -pedantic tests/controller_test.cpp -o /tmp/traffic-controller-test
/tmp/traffic-controller-test
```

Run the synthetic-image and HTTP tests using the [browser camera test instructions](browser_camera/README.md#test-the-host-on-any-platform).

On the model, check the fixed cycle with the Uno alone. Then connect the gateway and try A = 1 and B = 4. B’s next green should last 16 seconds. Change a count during green and check that the active phase runs to completion. Close the sender, wait five seconds and confirm the next green lasts 10 seconds. Throughout the cycle, only one road should show green at a time.

## References

- [Espressif Wi-Fi API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html)
- [Espressif WebServer example](https://github.com/espressif/arduino-esp32/blob/master/libraries/WebServer/examples/WebServer/WebServer.ino)
- [Arduino SoftwareSerial](https://docs.arduino.cc/learn/built-in-libraries/software-serial)
- [PlatformIO source file filters](https://docs.platformio.org/en/stable/projectconf/sections/env/options/build/build_src_filter.html)

# INT4089 Smart Traffic Light

This classroom model uses six LEDs to control a crossing between two one-way roads, A and B. An Arduino Uno R3 alternates the lights and runs a fixed cycle on its own. With an ESP32 connected, the Uno can give the road with the longer queue up to 10 extra seconds of green. Enter queue lengths manually, or run the browser dashboard on a computer to count model cars using a computer webcam or a phone camera.

## Hardware and wiring

Use an Arduino Uno R3, a classic ESP32-WROOM-32 development board with GPIO16 and GPIO17 available, two USB cables, jumper wires, six low-current LEDs (two each of red, yellow and green), and six 1 kΩ resistors. Check the pinout and PlatformIO board setting before using an ESP32-C3, S3, WROVER or ESP32-CAM.

Disconnect power before wiring. For each LED, connect the Uno pin through its own **1 kΩ resistor** to the anode (long leg), then connect the cathode to GND. These connections assume individual low-current LEDs.

| Road | Red LED | Yellow LED | Green LED |
| --- | --- | --- | --- |
| A (north–south) | D2 | D3 | D4 |
| B (east–west) | D5 | D6 | D7 |

| ESP32 | Uno | Purpose |
| --- | --- | --- |
| GPIO17 (TX) | D10 (RX) | One-way serial commands at 9600 baud |
| GND | GND | Common ground |

Power each board through its own USB cable. Keep the boards’ 5 V and 3.3 V supply pins separate. Leave Uno D11 and ESP32 GPIO16 disconnected to keep the Uno’s 5 V output away from the ESP32 GPIO. Use a short wire for the serial signal. The Uno firmware disables the internal 5 V pull-up on D10. If reception is unreliable, use a UART-compatible 3.3 V to 5 V level shifter.

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

The Uno firmware is in [arduino_uno](arduino_uno), including the timing logic in [TrafficController.h](arduino_uno/TrafficController.h). The ESP32 can join the computer's Wi-Fi network, serves a fallback manual page and forwards commands from [esp32_gateway.cpp](esp32_gateway/esp32_gateway.cpp).

Serial port names vary by host. Use the actual COM port on Windows or the actual `/dev/ttyUSB*` or `/dev/ttyACM*` port on Linux.

## Use the browser dashboard

Run the dashboard on a Mac, Linux PC or Windows PC. The ESP32 joins the computer's Wi-Fi hotspot or a shared router. Open the dashboard on the computer to use its built-in or USB camera, or open the computer's HTTPS address on an Android phone or iPhone to use the phone camera. The computer processes the images and sends the counts to the ESP32. See the [browser camera setup and calibration guide](browser_camera/README.md).

## Try the direct manual controls

1. Power both boards. Join **TrafficLight-Lab** on your phone using the password **traffic123**. Stay connected if the phone reports that the network has no internet access.
2. Open **http://192.168.4.1**. The ESP32 also prints its address to the USB serial monitor at 115200 baud.
3. On the Chinese-language page, enter **8** in the first field (road A) and **3** in the second (road B). Press the first button to apply the counts. Keep the page in the foreground so it can resend them every second. Press the same button again after editing either field.
4. Watch the next green phase for each road. With these counts, A gets **20 seconds** and B gets **10 seconds**. The page confirms receipt at the ESP32. To verify the Uno’s response, watch the LEDs or check the phase and duration in its USB serial monitor at 115200 baud.
5. Press the second button to return to fixed timing. If you close the page or disconnect, the Uno falls back to fixed timing five seconds after the last count.

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
- [Espressif WebServer example](https://github.com/espressif/arduino-esp32/blob/master/libraries/WebServer/examples/WebServer/WebServer.cpp)
- [Arduino SoftwareSerial](https://docs.arduino.cc/learn/built-in-libraries/software-serial)
- [PlatformIO source file filters](https://docs.platformio.org/en/stable/projectconf/sections/env/options/build/build_src_filter.html)

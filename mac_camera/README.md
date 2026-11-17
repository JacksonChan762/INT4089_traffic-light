# Count model cars with an iPhone and a Mac

The iPhone supplies an overhead view of the intersection. The Mac compares each road’s waiting area with an image of the empty road, counts the objects and sends the two totals to the ESP32 over Wi-Fi. Video frames stay on the Mac. The tool works with the firmware in the [main project](../README.md).

## Connect the iPhone camera

1. Enable Continuity Camera on the iPhone under **Settings → General → AirPlay & Continuity**. Menu names vary by iOS version. Both devices need compatible software and the same Apple Account with two-factor authentication. [Apple’s Continuity Camera setup guide](https://support.apple.com/en-us/102546)
2. Connect the iPhone to the Mac over USB and trust the computer if prompted. Keep Wi-Fi and Bluetooth enabled and Personal Hotspot off. Lock the iPhone and mount it with its rear camera facing both waiting areas.
3. Open **New Movie Recording** in QuickTime Player and select the iPhone from the camera menu to check the framing. Close the preview to release the camera. Turn off Center Stage, portrait blur and background effects so the image stays steady.
4. If macOS requests camera access, grant it to the app running Python. You can review access under **System Settings → Privacy & Security → Camera**.

## Install and launch

While the Mac has internet access, run these commands from the repository root:

```sh
cd mac_camera
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Power the Uno and ESP32 and connect their serial signal and ground as shown in the [wiring guide](../README.md#hardware-and-wiring). Close any browser page sending manual counts. Join **TrafficLight-Lab** on the Mac using the password **traffic123**. USB carries the camera feed and Wi-Fi carries the counts.

Double-click `Start.command` and try camera index `0`. If the built-in camera opens, press **q**, relaunch and try `1` or `2`. You can also select a camera from the terminal while in the `mac_camera` directory:

```sh
.venv/bin/python camera_control.py --camera 1
```

If the iPhone is missing, check its feed in QuickTime, close other camera apps and retry. Camera indexes can vary with the Mac and the OpenCV version. If QuickTime sees the iPhone but the tool cannot open it, check the camera permission and the error printed in the terminal.

## Calibrate and send counts

1. Use a plain road surface that contrasts with the cars. Keep the phone and lighting steady.
2. Click the preview and press **r**. Drag a rectangle around road A’s waiting area and press **Enter**. Repeat for road B. Keep the rectangles separate and exclude the center of the intersection, signals and exit lanes.
3. Remove all cars and hands, wait for the exposure to settle, then press **b** to capture the empty background. Repeat this setup each time you start the tool.
4. Place the cars in the waiting areas with a visible gap between them. Aim for at least 10 pixels between cars in the preview. Move your hands away and check the green boxes and the A/B totals.
5. Press **s** when the counts look right. The tool waits for three consecutive matching results and sends at most once per second. The status confirms that the ESP32 accepted the counts. Watch the LEDs to check the physical response.
6. Press **p** to stop sending and request fixed timing. Press **q** to quit.

## Tune the detector

Raise **Difference threshold** if small changes in brightness trigger detections. Raise **Minimum car area** to filter out small specks, or lower it if the tool misses small cars. Let the counts settle after each adjustment. If the camera or lighting moves, clear both roads and capture a new background with **b**. Select the waiting areas again if the framing has changed.

The detector counts objects that differ from the empty background, including stationary cars. Hands or shadows can add false detections, touching cars can merge into one, and reflections or low contrast can distort the count. [OpenCV connected components reference](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html)

Large scene changes, oversized objects or a loss of fresh frames interrupt count updates. Five seconds after the last valid count, the Uno uses 10 seconds for the next green. If the preview freezes while the camera driver keeps returning the same image, press **p** to stop sending.

## Verify the setup

| Action | Expected result |
| --- | --- |
| Clear both roads | A = 0 and B = 0 |
| Place three cars on A and one on B, then enable sending | A = 3 and B = 1. A’s next green lasts 14 seconds and B’s lasts 10 seconds. |
| Leave cars stationary, then remove them one at a time | Counts stay steady while parked and decrease as cars leave. |
| Press **p** | The next green lasts 10 seconds. |
| Disconnect the camera or quit | Count updates stop and the Uno returns to fixed timing. |

Run the automated tests from the `mac_camera` directory:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The tests use synthetic images to check empty roads, separated objects, lane boundaries, noise, major scene changes and count stability. A local mock server checks the ESP32 request format. Use the checks above to verify the actual camera, lighting and model cars.

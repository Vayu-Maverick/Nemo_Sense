# Setup Guide — NEMO_SENSE

> This guide assumes you have the hardware assembled and wired as described in `hardware_wiring.md`. If not, do that first.

We're going to be honest — the first time we got this running it took us about 3 hours because of a driver issue with the USB camera on Windows. This guide includes all the problems we ran into so hopefully it takes you 30 minutes.

---

## Requirements

### Hardware
- Arduino UNO Q (ABX00087) — flashed with motor_controller.ino
- Robot chassis assembled per `hardware_wiring.md`
- USB camera connected to Arduino UNO Q USB-A port
- 7.4V LiPo connected and charged
- A Windows or Linux PC/laptop connected to Arduino via USB cable (for first setup only)

### Software — PC side
- Python 3.10 or higher (3.11 recommended)
- Arduino IDE 2.x (for flashing firmware)
- Git (optional, for pulling updates)

---

## Step 1 — Flash the Arduino Motor Controller

1. Open **Arduino IDE 2**
2. Go to File → Open → navigate to `arduino/motor_controller/motor_controller.ino`
3. In the board selector at top, select **"Arduino UNO R4 Minima"** (the UNO Q shows as UNO R4)
4. Select the correct COM port (usually shows up as "Arduino UNO R4" in the port list)
5. Click Upload
6. Wait for "Done uploading"

**Verify it worked**: Open Serial Monitor at 115200 baud. You should see:
```
[NEMO_SENSE Motor Controller] Ready
Waiting for commands...
```

If you see garbage characters — your baud rate in Serial Monitor is wrong. Set it to 115200.

---

## Step 2 — Test the motors before running the full brain

This saves a lot of time. Run the motor test script first to confirm wiring:

```bash
python test_motors.py --port COM4
```

Replace `COM4` with your actual Arduino port. On Linux it's something like `/dev/ttyACM0`.

The script will run each motor individually — left forward, left backward, right forward, right backward, then both together. Watch the wheels and confirm:
- Left wheel rotates correctly for each command
- Right wheel rotates correctly
- No sparks, no excessive heat from relays

If a wheel goes the wrong direction — see hardware_wiring.md troubleshooting section.

---

## Step 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

The requirements.txt has:
```
opencv-python
pyserial
numpy
```

That's it. We kept dependencies minimal on purpose. No TensorFlow, no PyTorch — the ONNX model runs through OpenCV's built-in DNN module which doesn't need any extra AI framework installed.

> If pip install fails with permission errors on Windows, try `pip install --user -r requirements.txt`

> If opencv-python fails to install on Raspberry Pi, use `pip install opencv-python-headless` instead (no GUI, smaller, works fine for our use case)

---

## Step 4 — Verify the camera

Quick check before running the full brain:

```python
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
print("Camera OK" if ret else "Camera FAILED - try index 1 or 2")
cap.release()
```

Or just run `q_brain.py --show` and it will open a debug window showing what the camera sees with obstacle detection boxes overlaid.

---

## Step 5 — Find your Arduino port

If you're not sure which COM port the Arduino is on:

```bash
python find_arduino.py
```

Output example:
```
Scanning serial ports...
COM3: Silicon Labs CP210x - NOT Arduino
COM4: Arduino UNO R4 @ 115200 - MATCH ✓
COM7: USB Serial Device - NOT Arduino
```

---

## Step 6 — Run the AI brain

```bash
# Basic run
python q_brain.py --port COM4

# With visual debug window (shows camera feed + obstacle detection)
python q_brain.py --port COM4 --show

# Disable WiFi sensing if getting errors
python q_brain.py --port COM4 --no-wifi

# Full options
python q_brain.py --help
```

When running correctly you'll see output like:
```
Connected to MCU on COM4
Loading YOLOv5n model... done (1.2s)
Bluetooth server listening on port 1...
WiFi sensing background scanner started
Auto-navigating...
Moving towards North... (Heading: 0.02 rad, L:148 R:152)
Moving towards North... (Heading: 0.01 rad, L:150 R:150)
Obstacle detected (Vision). Avoiding!
```

---

## Step 7 — Connect the Android App (Optional)

The phone app is optional — the robot navigates on its own. The app adds:
- Voice commands ("stop", "go left", etc.)
- GPS-based destination guidance
- TTS audio feedback (the robot "speaks" through your phone)

To build and install:
1. Open the `android/` folder in **Android Studio**
2. Connect your phone via USB with USB debugging enabled
3. Click Run (green triangle)
4. App installs and opens
5. Tap "Connect" — it will scan for Bluetooth devices
6. Select "NEMO_SENSE" from the list
7. You'll see "Connected" and the robot will beep twice to confirm

> First time pairing: Your phone will ask for a PIN. Use **1234** (the default for most Bluetooth modules).

---

## Autostart on Raspberry Pi (for permanent deployment)

If you're deploying on a Raspberry Pi 4 attached to the robot (instead of a laptop):

```bash
chmod +x scripts/setup_q.sh
./scripts/setup_q.sh
```

This script:
1. Installs all Python dependencies
2. Copies the systemd service file
3. Enables autostart on boot

After running, the robot will start the AI brain automatically every time it powers on. No keyboard or monitor needed.

---

## Common Setup Problems

**"ModuleNotFoundError: No module named 'cv2'"**  
Run `pip install opencv-python` again. If still failing, check your Python version — needs to be 3.8+.

**"serial.SerialException: could not open port COM4"**  
The Arduino IDE Serial Monitor might still be open. Close it. Only one program can use the serial port at a time.

**"YOLOv5n model not found"**  
The `yolov5n.onnx` file needs to be in the same directory as `q_brain.py`. Check that it's there. It's a 7MB file — if it downloaded corrupted it might be smaller than expected.

**Robot runs but motors don't move**  
The `q_brain.py` connects to the motor controller via serial and sends `MOTOR:left,right` commands. If the motor controller received wrong firmware (old version with different command format), it won't understand. Re-flash `motor_controller.ino` and test with `test_motors.py` first.

**Bluetooth not connecting on Linux**  
Try `sudo python q_brain.py` — Bluetooth RFCOMM on Linux sometimes needs root. Alternatively, add your user to the `bluetooth` group: `sudo usermod -aG bluetooth $USER` then re-login.

**Camera works but detection is slow/bad**  
Make sure confidence threshold is not too high. Default is 0.45. If the environment is challenging (dark, cluttered) try lowering to 0.35 in `q_brain.py` (`CONFIDENCE_THRESHOLD = 0.35`). Also make sure the camera is not zoomed in on something close — the model expects a field of view of at least 60 degrees.

---

*Questions or issues? Raise a GitHub issue or check the competition report in `docs/competition_report.md`*

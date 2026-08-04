# Nemo~Sense
### Autonomous Navigational Aid for Visually Challenged Individuals

> *See with technology. Move with confidence.*

---

## Overview
Nemo~Sense is a self-contained, camera-guided rover that helps visually impaired users navigate indoor and outdoor environments. It uses a 720p webcam and on-device AI (YOLOv5n) to detect obstacles and steer around them autonomously — no phone, no internet, no cloud required.

**Hardware required:**
- Arduino UNO Q (Linux AI brain + STM32 motor bridge)
- Quarky chassis (wheels + motors)
- Logitech 720p USB webcam
- Powered USB hub
- 10 000 mAh power bank

---

## Quick Start

### 1. Flash the Arduino firmware
Connect the Arduino UNO Q to your PC via USB, then open the Arduino IDE or arduino-cli:
```
arduino-cli compile --fqbn arduino:zephyr:unoq arduino/motor_controller
arduino-cli upload  --fqbn arduino:zephyr:unoq arduino/motor_controller -p COMX
```
*(Replace `COMX` with your port, e.g. `COM3` on Windows)*

### 2. Push the Python code to the board
```bat
adb push python/ /home/arduino/nemosense/python/
```

### 3. Install Python dependencies (run once on the board)
```bash
pip3 install opencv-python numpy
```

### 4. Set up auto-start
Run `setup_autostart.bat` on your PC while the board is connected via USB. The rover will auto-start every time the battery is plugged in.

### 5. Manual run (for testing)
```bash
python3 /home/arduino/nemosense/python/main.py --mode full
```

---

## How it works

```
Webcam → YOLOv5n (obstacle detection)
                 ↓
         Micro-navigator (steer LEFT / RIGHT / STOP)
                 ↓   (overrides ↑ when obstacle present)
         Macro-navigator (north → east demo route)
                 ↓
         MotorLink  →  /dev/ttyACM0  →  STM32 MCU
                                              ↓
                                   GPIO D2/D3/D4
                                              ↓
                                        Quarky chassis
```

The rover drives **straight (north)** by default. If it detects an obstacle in the camera frame, it steers around it automatically. When no compass is available it just goes straight — no crash, no freeze.

---

## Wiring

| Arduino UNO Q | Quarky |
|---|---|
| D2 | Pin 1 (Right) |
| D3 | Pin 2 (Left) |
| D4 | Pin 3 (Stop) |
| GND | GND ← **required** |

USB hub connects: battery → hub → UNO Q (Type-C) + webcam + Quarky USB.

---

## Project Structure

```
nemosense/
├── arduino/
│   └── motor_controller/
│       └── motor_controller.ino   ← Flash this to the Arduino
├── python/
│   ├── main.py                    ← Main entry point
│   ├── config.py                  ← All settings
│   ├── vision.py                  ← Webcam + YOLOv5n
│   ├── micro_nav.py               ← Obstacle avoidance
│   ├── navigation.py              ← Waypoint navigation
│   └── motor_link.py              ← Serial bridge to MCU
├── quarky/
│   └── quarky_motor_control.py    ← PictoBlox logic reference
├── PATENT_DISCLOSURE.md           ← Technical disclosure
├── setup_autostart.bat            ← Install auto-start via ADB
└── README.md                      ← This file
```

---

## License
MIT License — free for personal, educational, and commercial use.

See [PATENT_DISCLOSURE.md](PATENT_DISCLOSURE.md) for a full technical description.

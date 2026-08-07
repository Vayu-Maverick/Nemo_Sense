# NEMO_SENSE 🦮
### Standalone AI Navigation Robot for the Visually Impaired
**Arduino Physical AI Challenge India 2026 — Robu.in × Arduino**

[![License: Unlicense](https://img.shields.io/badge/License-Unlicense-blue.svg)](https://unlicense.org)
[![Arduino UNO Q](https://img.shields.io/badge/Board-Arduino%20UNO%20Q-00979D?logo=arduino)](https://store.arduino.cc)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python)](https://python.org)
[![YOLOv5n](https://img.shields.io/badge/AI-YOLOv5n%20ONNX-EE4C2C)](https://github.com/ultralytics/yolov5)

---

> **285 million people** worldwide are visually impaired. Navigating a busy Indian city — with vehicles parked on footpaths, open manholes, stray animals, and uneven roads — is a daily challenge that a white cane alone cannot solve. NEMO_SENSE is our answer: a fully standalone, PC-free, internet-free AI navigation robot that detects obstacles in real time using a camera and guides the user through voice feedback on their phone. Total cost to build: **under ₹6,000**.

---

## Table of Contents

1. [The Problem](#the-problem)
2. [Our Solution](#our-solution)
3. [System Architecture](#system-architecture)
4. [Circuit Architecture](#circuit-architecture)
5. [Power System & Battery Mechanics](#power-system--battery-mechanics)
6. [Hardware](#hardware)
7. [AI & Software Architecture](#ai--software-architecture)
8. [Android App](#android-app)
9. [Repository Structure](#repository-structure)
10. [How to Build & Run](#how-to-build--run)
11. [Testing & Results](#testing--results)
12. [License](#license)

---

## The Problem

Navigation for visually impaired people in Indian cities involves obstacles that a white cane simply cannot warn about in time:

- Vehicles parked on footpaths and pedestrian zones
- Overhead obstacles — hanging branches, low signs, side mirrors
- Open manholes and broken tiles on footpaths
- Construction zones with sudden barriers
- Stray animals that move unpredictably
- Dense foot traffic that blocks the path suddenly

Existing solutions fall short in one way or another:
- **White cane**: Only detects ground-level obstacles within 1–2m, requires constant active sweeping, gives no directional info
- **GPS apps**: Require the user to look at a screen, do not detect physical obstacles
- **Guide dogs**: Cost ₹3–4 lakhs to train, waiting lists of years, not widely available in India
- **Commercial wearables**: Cost ₹20,000–2,00,000+, require internet, often need a caregiver to set up

We wanted something a student could build, a family could afford, and a blind person could actually use independently.

---

## Our Solution

NEMO_SENSE is a differential-drive mobile robot that:

1. **Detects obstacles** using YOLOv5n running on the Arduino UNO Q's NPU — in real time, on-device, no cloud
2. **Fuses sensor data** from a USB camera, WiFi RSSI shadow-fading, and an ultrasonic sensor for robust detection even in difficult lighting
3. **Navigates autonomously** using dead-reckoning wheel encoders and a P-controller — no GPS needed indoors
4. **Guides the user** through voice feedback sent via Bluetooth to their Android phone — TTS reads instructions aloud

**No PC. No internet. No cloud. The Arduino UNO Q does everything.**

---

## System Architecture

```
╔══════════════════════════════════════════════════════════════════════╗
║                        NEMO_SENSE ROBOT                              ║
║                                                                      ║
║  ┌─────────────┐    USB     ┌──────────────────────────────────┐    ║
║  │  USB Camera │───────────►│         Arduino UNO Q            │    ║
║  │  (720p)     │            │         (RA4M1 Cortex-M4)        │    ║
║  └─────────────┘            │                                  │    ║
║                             │  ┌──────────────────────────┐   │    ║
║  ┌─────────────┐   GPIO     │  │    Neural Processing Unit │   │    ║
║  │  HC-SR04    │───────────►│  │    YOLOv5n ONNX (7MB)    │   │    ║
║  │  Ultrasonic │            │  │    Obstacle Detection     │   │    ║
║  └─────────────┘            │  │    4–6 FPS Real-Time      │   │    ║
║                             │  └──────────────────────────┘   │    ║
║  ┌─────────────┐   WiFi     │                                  │    ║
║  │  WiFi Scan  │───────────►│  ┌──────────────────────────┐   │    ║
║  │  RSSI Fading│            │  │    Sensor Fusion Engine   │   │    ║
║  └─────────────┘            │  │    Vision + WiFi + Sonar  │   │    ║
║                             │  └──────────────────────────┘   │    ║
║  ┌─────────────┐  Interrupt │                                  │    ║
║  │  LM393 x2   │───────────►│  ┌──────────────────────────┐   │    ║
║  │  Encoders   │            │  │    Dead-Reckoning Odom    │   │    ║
║  └─────────────┘            │  │    P-Controller Steering  │   │    ║
║                             │  └──────────────────────────┘   │    ║
║                             │              │                   │    ║
║                             └──────────────┼───────────────────┘    ║
║                                            │ UART Serial             ║
║                             ┌──────────────▼───────────────────┐    ║
║                             │    Motor Controller Arduino       │    ║
║                             │    (arduino/motor_controller/)    │    ║
║                             └──────────────┬───────────────────┘    ║
║                                            │ GPIO                    ║
║                             ┌──────────────▼───────────────────┐    ║
║                             │    4-Channel Relay Module         │    ║
║                             │    (Active-LOW, 5V coil, 10A)    │    ║
║                             └──────┬──────────────┬────────────┘    ║
║                                    │              │                  ║
║                          ┌─────────▼──┐    ┌──────▼──────┐         ║
║                          │ Left Motor │    │ Right Motor │         ║
║                          │  DC Gear   │    │  DC Gear    │         ║
║                          └────────────┘    └─────────────┘         ║
║                                                                      ║
╚══════════════════════════════════════════════════════════╦═══════════╝
                                                           ║ Bluetooth RFCOMM
                                              ╔════════════▼══════════╗
                                              ║   Android Phone       ║
                                              ║   (Optional)          ║
                                              ║   • TTS Voice Output  ║
                                              ║   • Voice Commands    ║
                                              ║   • GPS Waypoints     ║
                                              ║   • Gemini AI NLP     ║
                                              ╚═══════════════════════╝
```

### Data Flow

```
Camera Frame (640×480)
        │
        ▼
  Resize → 640×640
  Normalize → [0,1]
        │
        ▼
  YOLOv5n NPU Inference
  Confidence threshold: 0.45
        │
        ▼
  Zone Classification
  LEFT (x<213) | CENTER (213-426) | RIGHT (x>426)
        │
        ├──────────────────────────────────────────┐
        ▼                                          ▼
  WiFi RSSI Shadow-Fading               HC-SR04 Ultrasonic
  (background thread, 2Hz)              (firmware level, 10Hz)
  EMA baseline tracking                 Hard-stop at <25cm
        │
        ▼
  Sensor Fusion (sensor_fusion.py)
  Fuse: vision zones + WiFi confidence + sonar distance
        │
        ▼
  Navigation Decision
  ┌─────────────┬──────────────┬───────────────┐
  │  FORWARD    │   AVOID LEFT │  AVOID RIGHT  │
  │  (clear)    │  (obs right) │  (obs left)   │
  └─────────────┴──────────────┴───────────────┘
        │
        ▼
  P-Controller (heading error × Kp=100)
  left_speed = base - turn
  right_speed = base + turn
        │
        ▼
  UART → Motor Controller → Relay Module → Motors
        │
        ▼
  Bluetooth → Android TTS → User hears guidance
```

---

## Circuit Architecture

### Full Schematic (block level)

```
                    ┌──────────────────────────────────────────┐
                    │            ARDUINO UNO Q                 │
                    │                                          │
  USB-A Host ───────┤← USB Camera (UVC, 720p)                  │
                    │                                          │
  D2 (GPIO OUT) ────┤→ Relay IN1  (Left Motor FORWARD)         │
  D3 (GPIO OUT) ────┤→ Relay IN2  (Left Motor BACKWARD)        │
  D4 (GPIO OUT) ────┤→ Relay IN3  (Right Motor FORWARD)        │
  D5 (GPIO OUT) ────┤→ Relay IN4  (Right Motor BACKWARD)       │
                    │                                          │
  D8 (GPIO OUT) ────┤→ Active Buzzer (+)                       │
                    │                                          │
  D12 (GPIO OUT) ───┤→ HC-SR04 TRIG                            │
  D11 (GPIO IN)  ───┤← HC-SR04 ECHO                            │
                    │                                          │
  D6 (INT) ─────────┤← Left Encoder OUT  (LM393)              │
  D7 (INT) ─────────┤← Right Encoder OUT (LM393)              │
                    │                                          │
  TX0 ─────────────┤→ Motor Controller RX (UART 115200)       │
  RX0 ─────────────┤← Motor Controller TX (UART 115200)       │
                    │                                          │
  A0 (ADC) ─────────┤← BAT-1 Voltage Divider                  │
  A1 (ADC) ─────────┤← BAT-2 Voltage Divider                  │
  A2 (ADC) ─────────┤← BAT-3 Voltage Divider                  │
                    │                                          │
  VIN (5V) ─────────┤← 5V from LM2596 Buck Converter          │
  GND ──────────────┤← Common Ground                          │
                    └──────────────────────────────────────────┘


  ┌──────────────────────────────────────────┐
  │         4-CHANNEL RELAY MODULE           │
  │                                          │
  │  VCC ────────────── 5V rail              │
  │  GND ────────────── Common GND           │
  │  IN1 ←─────────── D2 (Arduino)          │
  │  IN2 ←─────────── D3 (Arduino)          │
  │  IN3 ←─────────── D4 (Arduino)          │
  │  IN4 ←─────────── D5 (Arduino)          │
  │                                          │
  │  CH1 COM ←── Battery (+) via 5A fuse    │
  │  CH1 NO  ──► Left Motor terminal A      │
  │  CH2 COM ←── Battery (+) via 5A fuse    │
  │  CH2 NO  ──► Left Motor terminal B      │
  │  CH3 COM ←── Battery (+) via 5A fuse    │
  │  CH3 NO  ──► Right Motor terminal A     │
  │  CH4 COM ←── Battery (+) via 5A fuse    │
  │  CH4 NO  ──► Right Motor terminal B     │
  └──────────────────────────────────────────┘


  Motor Direction Truth Table (Active-LOW relay):
  ┌────────────┬────┬────┬────────────────────┐
  │  Command   │ IN1│ IN2│   Left Motor        │
  ├────────────┼────┼────┼────────────────────┤
  │  FORWARD   │ 0  │ 1  │ CH1 closed, CH2 open│
  │  BACKWARD  │ 1  │ 0  │ CH1 open, CH2 closed│
  │  STOP      │ 1  │ 1  │ Both open (freewheel)│
  └────────────┴────┴────┴────────────────────┘
  (Same logic applies to IN3/IN4 for Right Motor)


  Voltage Divider for Battery Monitoring:
  (same circuit × 3 for BAT-1, BAT-2, BAT-3)

  Battery (+) ─── R1 (10kΩ) ─── ADC pin ─── R2 (3.3kΩ) ─── GND

  Scale factor: ADC reading × (R1+R2)/R2 × (3.3V / 1023)
              = ADC × (13.3/3.3) × 0.003226
```

### Relay Coil Protection

Each relay coil **must** have a flyback diode or it will spike 50–100V back into the GPIO pin when de-energised:

```
  Arduino D2 ──────────┬──── Relay IN1 coil (+)
                       │
                     [1N4007]  ← Flyback diode (cathode to VCC side)
                       │
  5V rail ─────────────┴──── Relay IN1 coil (-)

  (Repeat for all 4 relay channels)
```

### Emergency Stop Circuit

A normally-closed (NC) push button on the main relay power rail. Pressing it instantly cuts all motor power regardless of software state:

```
  Battery (+) ──[5A FUSE]──[NC BUTTON]──► Relay COM terminals
```

---

## Power System & Battery Mechanics

NEMO_SENSE uses **three independent battery units** in a deliberate redundancy design. The key insight is that BAT-1 and BAT-2 are **completely identical** — same type, same voltage, same capacity — and serve the same function. When BAT-1 depletes, BAT-2 takes over automatically with no interruption.

### Full Power Distribution Diagram

```
BAT-1: 7.4V LiPo 2200mAh  ──[1N5822 Schottky]──┐
                                                  │
BAT-2: 7.4V LiPo 2200mAh  ──[1N5822 Schottky]──┤
                                                  │
                                         ┌────────▼─────────┐
                                         │  MAIN POWER RAIL  │
                                         │     ~7.4V         │
                                         └────────┬──────────┘
                                                  │
              ┌───────────────────────────────────┼──────────────────────────┐
              │                                   │                          │
    ┌─────────▼─────────┐             ┌───────────▼──────────┐   ┌──────────▼──────────┐
    │  [5A BLADE FUSE]  │             │  LM2596 Buck Conv.   │   │  Voltage Dividers   │
    │         │         │             │  7.4V → 5.0V         │   │  → A0 (BAT-1 mon.)  │
    │  Relay COM ports  │             └───────────┬──────────┘   │  → A1 (BAT-2 mon.)  │
    │    (all 4 ch)     │                         │              └─────────────────────┘
    └────────┬──────────┘             ┌───────────▼──────────────────────────────┐
             │                        │              5V LOGIC RAIL               │
    ┌────────▼──────────┐             │  Arduino UNO Q (VIN)                     │
    │  DC Drive Motors  │             │  4-CH Relay Module (VCC)                 │
    │  (full 7.4V)      │             │  HC-SR04 Ultrasonic (VCC)                │
    └───────────────────┘             │  LM393 Encoders × 2 (VCC)               │
                                      │  USB Camera (via Arduino USB-A)          │
                                      └──────────────────────────────────────────┘


BAT-3: 3.7V 18650 Li-ion (800mAh) — COMPLETELY INDEPENDENT RAIL
       │
       ├──► Active Buzzer (always connected, not switched)
       ├──► Bluetooth module VCC (always connected)
       └──► Voltage divider → Arduino A2 (BAT-3 monitor)
```

### How the Automatic Failover Works

BAT-1 and BAT-2 are both connected to the main rail through **1N5822 Schottky diodes** (cathodes joined). This creates a passive OR circuit:

- Whichever battery has the **higher terminal voltage** supplies all the current
- As BAT-1 discharges, its terminal voltage slowly drops (~7.4V → ~6.8V over 1.5hrs)
- BAT-2 (fresher, still at ~8.2V) automatically begins supplying more current
- The transition is **completely seamless** — no relay click, no software, no reset
- Once BAT-1 is fully depleted, BAT-2 carries the full load alone

**Why Schottky and not regular 1N4007?**  
Regular diodes have a 0.6–0.7V forward voltage drop, which means the 7.4V battery only delivers ~6.7V to the rail — borderline for reliable motor operation. Schottky diodes drop only ~0.3V, so the rail sees ~7.1V. Worth the slight cost increase.

### Why BAT-3 is Separate

BAT-3 (3.7V 18650, 800mAh) powers only the buzzer and Bluetooth module, and it is **always live** — it has no switch. This means:

- Even if both main batteries die completely and the Arduino resets, the Bluetooth module is still transmitting
- The Android app detects the Bluetooth disconnect and immediately alerts the user
- The buzzer emits 5 short beeps to signal power failure
- User is **never** left with zero feedback about the robot's state

This is especially critical for a blind user who cannot visually inspect the robot.

### Battery Current Budget

| Consumer | Rail | Current Draw |
|---|---|---|
| Left DC Motor (moving, no load) | BAT1/2 7.4V | ~200mA |
| Left DC Motor (at load) | BAT1/2 7.4V | ~500mA |
| Right DC Motor (at load) | BAT1/2 7.4V | ~500mA |
| Arduino UNO Q | 5V logic | ~200mA |
| USB Camera | 5V via USB-A | ~250mA |
| 4-CH Relay Module (4 coils active) | 5V logic | ~60mA |
| HC-SR04 Ultrasonic | 5V logic | ~15mA |
| LM393 Encoders × 2 | 5V logic | ~20mA |
| Active Buzzer | BAT3 3.7V | ~30mA |
| Bluetooth module | BAT3 3.7V | ~50mA |
| **Peak total (7.4V rail)** | | **~1.5A** |
| **Logic rail total (5V)** | | **~545mA** |

### Runtime Estimates

| Scenario | Runtime |
|---|---|
| BAT-1 alone, normal navigation | ~1.5 hrs |
| BAT-1 → BAT-2 failover, combined | **~3 hrs total** |
| BAT-3 (emergency buzzer + BT) | ~18 hrs standby |

### Battery Monitoring Thresholds (in `q_brain.py`)

```python
BAT1_LOW_V  = 6.8   # Voice: "Primary battery low, switching to backup"
BAT2_LOW_V  = 6.8   # Voice: "Backup battery also low. Stopping in 60 seconds."
BAT3_LOW_V  = 3.3   # Buzzer only (logic may be off)
```

---

## Hardware

### Bill of Materials

| Component | Model / Spec | Qty | Approx Cost (INR) |
|---|---|---|---|
| Arduino UNO Q | ABX00087, RA4M1 + NPU | 1 | ₹3,200 |
| 4-Channel Relay Module | 5V coil, 10A contacts | 1 | ₹150 |
| DC Gear Motor with encoder | 6V, 1:48 ratio, TT motor | 2 | ₹600 |
| 65mm Rubber Wheels | Fits TT motor shaft | 2 | ₹120 |
| USB Camera | 720p, UVC standard | 1 | ₹450 |
| HC-SR04 Ultrasonic | 2cm–400cm range | 1 | ₹50 |
| LM393 Wheel Encoder | 20-slot disc included | 2 | ₹100 |
| Active Buzzer | 5V, 85dB | 1 | ₹20 |
| 7.4V LiPo 2200mAh | 2S, XT30 connector | 2 | ₹1,200 |
| 3.7V 18650 Li-ion | 800mAh, protected | 1 | ₹150 |
| LM2596 Buck Converter | 7.4V→5V, 3A rated | 1 | ₹80 |
| 1N5822 Schottky Diode | 40V/3A | 2 | ₹20 |
| 1N4007 Diode | Relay flyback × 4 | 4 | ₹10 |
| 5A Automotive Blade Fuse + holder | For motor battery line | 1 | ₹30 |
| Resistors 10kΩ + 3.3kΩ | Voltage dividers × 3 | 6 | ₹10 |
| NC Push Button | Emergency stop | 1 | ₹20 |
| Acrylic sheet 30×20cm | Chassis base | 1 | ₹150 |
| M3 standoffs, screws, nuts | Hardware | - | ₹100 |
| Jumper wires (M-M, M-F, F-F) | Assorted | - | ₹80 |
| **TOTAL** | | | **≈ ₹6,540** |

### Physical Assembly

The chassis is a 30×20cm acrylic sheet cut into a rectangular base. Components are mounted on two levels using M3 standoffs:

```
TOP VIEW (approximate layout):

┌──────────────────────────────────────┐
│  [Camera mount]    [Arduino UNO Q]   │
│                                      │
│  [Relay Module]    [Buck Converter]  │
│                                      │
│  [HC-SR04]         [Bluetooth mod]   │
└──────────────────────────────────────┘

BOTTOM VIEW:
┌──────────────────────────────────────┐
│  [Left Motor]           [Right Motor]│
│     │                       │        │
│  [Encoder]              [Encoder]   │
│                                      │
│  [BAT-1 LiPo]   [BAT-2 LiPo]       │
│                                      │
│  [BAT-3 18650]                       │
└──────────────────────────────────────┘

Dimensions: 25cm × 20cm × 15cm (with camera)
Weight with batteries: ~950g
```

---

## AI & Software Architecture

### Python Module Map

```
python/
├── main.py            ← Entry point — orchestrates all modules
├── vision.py          ← YOLOv5n ONNX inference via OpenCV DNN
├── sensor_fusion.py   ← Fuses vision + WiFi + sonar into zone confidence
├── navigation.py      ← High-level route planning and obstacle avoidance
├── motor_link.py      ← Serial UART interface to motor controller Arduino
├── dead_reckoning.py  ← Odometry from encoder ticks → x,y,heading
├── micro_nav.py       ← Low-level P-controller for heading correction
├── wifi_sensing.py    ← WiFi RSSI scanner and shadow-fading detector
├── lidar_map.py       ← Optional 2D occupancy grid (if LiDAR attached)
├── speed_learner.py   ← Adaptive speed based on environment density
├── ble_server_win.py  ← Windows Bluetooth RFCOMM server
├── bt_server.py       ← Linux/Pi Bluetooth RFCOMM server
├── config.py          ← All tunable constants (thresholds, ports, etc.)
└── models/
    └── yolov5n.onnx   ← 7MB obstacle detection model
```

Also at root level:
- `q_brain.py` — alternative single-file brain (all modules merged, simpler deployment)
- `rover_simulator.py` — software-in-the-loop simulator, no hardware needed for testing

### Vision System (vision.py)

```python
Input:  640×480 camera frame
Process:
  1. Resize to 640×640
  2. Normalize: pixel / 255.0
  3. Create blob: cv2.dnn.blobFromImage(...)
  4. Forward pass through YOLOv5n ONNX via OpenCV DNN
  5. Confidence filter: > 0.45
  6. Zone assignment by bounding box center X:
       x < 213px  → LEFT
       213–426px  → CENTER
       x > 426px  → RIGHT
  7. Proximity estimation: bounding box area / frame area

Output: List of {zone, proximity, class_id, confidence}
```

### WiFi Shadow-Fading Sensor (wifi_sensing.py)

```python
Principle:
  When a large object (person, vehicle) passes between robot and
  an access point, it absorbs WiFi signal → measurable RSSI drop.

Algorithm:
  1. Scan all visible APs every 500ms
  2. Maintain EMA baseline RSSI per BSSID:
       baseline = α × current_rssi + (1-α) × baseline   [α=0.1]
  3. Shadow-fading threshold: current drops > 6dB below baseline
  4. Count APs showing simultaneous fading → obstacle confidence
  5. Distribute confidence to LEFT/CENTER/RIGHT zones (heuristic)

Works best: indoors with many APs (school corridors, malls)
Works poorly: outdoors with few APs
```

### Sensor Fusion (sensor_fusion.py)

```python
Per zone (LEFT, CENTER, RIGHT):
  fused_confidence[zone] = max(
      vision_confidence[zone],         # Camera detection
      wifi_confidence[zone] * 0.6,     # WiFi (lower weight — less reliable)
  )

  # Hard override: ultrasonic within 25cm = always stop (firmware level)

Decision:
  if fused_confidence["center"] > 0.5:  → STOP / AVOID
  elif fused_confidence["right"] > 0.5: → STEER LEFT
  elif fused_confidence["left"] > 0.5:  → STEER RIGHT
  else:                                  → FORWARD (clear path)
```

### Dead-Reckoning Odometry (dead_reckoning.py)

```python
Hardware: LM393 optical encoders, 20-slot discs
Wheel:    65mm diameter, circumference = π × 65 = 204mm
Per tick: 204mm / 20 = 10.2mm travel

State update (per encoder interrupt):
  dl = left_ticks_delta  × 10.2mm
  dr = right_ticks_delta × 10.2mm
  dc = (dl + dr) / 2
  dθ = (dr - dl) / wheel_base_mm   [wheel_base = 150mm]

  x += dc × cos(θ + dθ/2)
  y += dc × sin(θ + dθ/2)
  θ += dθ
```

### P-Controller Steering (micro_nav.py)

```python
target_heading = 0.0   # North (or GPS-derived bearing)
error = target_heading - current_heading
# Normalize to [-π, π]

Kp = 100
turn = int(error × Kp)

base_speed = 150   # 0–255 scale
# Reduce speed in dense environments (WiFi signal quality proxy)
base_speed = int(base_speed × (0.5 + 0.5 × wifi_signal_quality))

left_speed  = clamp(base_speed - turn, 0, 255)
right_speed = clamp(base_speed + turn, 0, 255)
```

---

## Android App

Located in `android/` — built with Kotlin, targets Android 10+.

### Features

| Feature | Implementation |
|---|---|
| Bluetooth connection | `BluetoothManager.kt` — RFCOMM socket to robot |
| Voice commands | `VoiceHelper.kt` — Android SpeechRecognizer API |
| TTS output | `VoiceHelper.kt` — Android TextToSpeech engine |
| GPS navigation | `LocationHelper.kt` — FusedLocationProvider |
| Route planning | `RouteHelper.kt` — bearing calculation to waypoint |
| Gemini AI NLP | `GeminiHelper.kt` — Gemini 1.5 Flash (experimental) |
| Main UI | `MainActivity.kt` — status, connect button, live map |

### App ↔ Robot Communication

The app and robot exchange JSON messages over Bluetooth RFCOMM:

```json
// Robot → App (status update, sent every 1 second)
{
  "type": "status",
  "obstacle": "center",
  "confidence": 0.82,
  "heading_rad": 0.12,
  "x_cm": 45.3,
  "y_cm": 12.1,
  "bat1_v": 7.21,
  "bat2_v": 8.14,
  "speak": "Obstacle ahead. Moving right."
}

// App → Robot (user voice command)
{
  "type": "command",
  "action": "stop"
}

// App → Robot (GPS waypoint bearing)
{
  "type": "waypoint",
  "bearing_deg": 47.3
}
```

### App Screenshot Flow

```
[Connect Screen] → tap "CONNECT" → BT scan → select NEMO_SENSE
       ↓
[Navigation Screen]
  Top:    Battery indicators (BAT-1, BAT-2, BAT-3)
  Center: Live ASCII zone map (LEFT | CENTER | RIGHT obstacle confidence)
  Bottom: "Listening..." / voice command display
  Log:    Scrolling TTS message history
```

---

## Repository Structure

```
Nemo_Sense/
│
├── README.md                        ← You are here
├── UNLICENSE                        ← Public domain
├── .gitignore
│
├── q_brain.py                       ← Single-file AI brain (all-in-one)
├── requirements.txt                 ← pip dependencies
├── yolov5n.onnx                     ← Obstacle detection model (7MB)
│
├── python/                          ← Modular brain (use this for development)
│   ├── main.py
│   ├── vision.py
│   ├── sensor_fusion.py
│   ├── navigation.py
│   ├── motor_link.py
│   ├── dead_reckoning.py
│   ├── micro_nav.py
│   ├── wifi_sensing.py
│   ├── lidar_map.py
│   ├── speed_learner.py
│   ├── ble_server_win.py
│   ├── bt_server.py
│   ├── config.py
│   └── models/
│       └── yolov5n.onnx
│
├── arduino/
│   └── motor_controller/
│       └── motor_controller.ino     ← Flash to Arduino UNO Q
│
├── q_mcu_motor/
│   └── q_mcu_motor.ino              ← Deprecated motor test sketch
│
├── android/                         ← Kotlin Android companion app
│   ├── app/src/main/java/com/netra/app/
│   │   ├── MainActivity.kt
│   │   ├── BluetoothManager.kt
│   │   ├── VoiceHelper.kt
│   │   ├── LocationHelper.kt
│   │   ├── GeminiHelper.kt
│   │   └── RouteHelper.kt
│   └── app/src/main/res/
│
├── docs/
│   ├── hardware_wiring.md           ← Full wiring + safety testing
│   ├── setup_guidesense.md          ← Step-by-step build and run guide
│   ├── competition_report.md        ← Full project report for judges
│   └── submission_guide.md          ← Pre-submission checklist
│
├── renders/
│   ├── cad/                         ← CAD renders of PCB + chassis
│   └── shots/                       ← Project visuals and AI shots
│
├── scripts/
│   ├── setup_q.sh                   ← One-shot Pi/SBC setup
│   └── run_netra.sh                 ← Autostart script
│
├── Test utilities (root level):
│   ├── test_webcam_ai.py            ← Test camera + YOLOv5n live
│   ├── test_motors.py               ← Verify motor wiring
│   ├── test_wifi_sensing.py         ← Verify WiFi RSSI scanning
│   ├── test_gps.py                  ← GPS / bearing test
│   ├── find_arduino.py              ← Auto-detect COM port
│   ├── find_serial.py               ← List all serial ports
│   └── rover_simulator.py           ← Full software-in-the-loop sim
│
└── Deployment tools:
    ├── deploy.bat                   ← Windows deploy script
    ├── push_to_unoq.bat             ← Upload firmware to UNO Q
    ├── autostart.sh                 ← Linux autostart
    ├── usb_host_init.sh             ← USB host mode init (Pi)
    └── setup_autostart.bat          ← Windows autostart setup
```

---

## How to Build & Run

**Full guide**: [`docs/setup_guidesense.md`](docs/setup_guidesense.md)  
**Wiring**: [`docs/hardware_wiring.md`](docs/hardware_wiring.md)

### Quick Start

```bash
# 1. Flash Arduino motor controller
#    Arduino IDE → arduino/motor_controller/motor_controller.ino
#    Board: Arduino UNO R4 Minima → Upload

# 2. Install Python deps
pip install -r requirements.txt

# 3. Test motors before anything else
python test_motors.py --port COM4

# 4. Run the AI brain
python q_brain.py --port COM4            # Windows
python q_brain.py --port /dev/ttyACM0   # Linux

# 5. Optional: with visual debug window
python q_brain.py --port COM4 --show

# 6. Optional: disable WiFi sensing
python q_brain.py --port COM4 --no-wifi
```

---

## Testing & Results

| Test | Result |
|---|---|
| Motor direction (50 runs) | 50/50 pass — correct direction every time |
| Emergency stop response | 47ms avg, 63ms max (from 25cm zone entry to full stop) |
| Battery failover (BAT-1 → BAT-2) | Seamless, robot continued without interruption |
| Continuous run endurance | 42 mins — relay temp 38°C, no issues |
| Blindfold navigation (20 trials) | **19/20 without collision (95%)** |
| 1 failure case | Glass door — transparent, camera cannot detect edges |

### Environment Results

| Environment | Obstacles Detected | Notes |
|---|---|---|
| School corridor (indoor) | 19/20 trials collision-free | Best performance, controlled lighting |
| Campus open area (outdoor) | 8/10 | Direct sunlight glare reduces confidence |
| Market street (outdoor, busy) | 7/10 | High crowd density confuses zone classification |

---

## License

This is free and unencumbered software released into the public domain.  
See [UNLICENSE](UNLICENSE) — do whatever you want with it.

---

*Built for Arduino Physical AI Challenge India 2026 · Robu.in × Arduino*  
*GitHub: https://github.com/Vayu-Maverick/Nemo_Sense*

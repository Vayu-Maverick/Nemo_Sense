# NEMO_SENSE 🦮
### AI-Powered Navigation Robot for Blind and Visually Impaired People
**Arduino Physical AI Challenge India 2026 — Robu.in × Arduino**

---

> We built NEMO_SENSE because 285 million people in the world are visually impaired and most of the assistive technology available is either too expensive or too complicated to use. Our robot uses the Arduino UNO Q's onboard neural processing unit to detect obstacles in real time using a camera, and guides the user through voice feedback on their phone. The whole thing costs under ₹5000 to build.

---

## ⚠️ IMPORTANT — which branch to look at

| Branch | What's in it | Who should look at it |
|---|---|---|
| [`production`](https://github.com/Vayu-Maverick/Nemo_Sense/tree/production) | Only the code that runs the robot | **Judges — start here** |
| [`main`](https://github.com/Vayu-Maverick/Nemo_Sense/tree/main) | Everything — android app, docs, all tools | Full project view |

---

## The Problem

Navigation for blind people in Indian cities is extremely hard. The footpaths are uneven, there are vehicles parked on roads, there are open manholes, stray animals and all sorts of obstacles that a white cane simply cannot detect until it's too late. Existing GPS apps assume the user can see the screen. Existing guide dogs are expensive to train (₹3-4 lakhs) and not widely available. We wanted to build something cheap, practical, and actually helpful.

---

## What NEMO_SENSE does

1. **Sees** — A USB camera feeds live video to the YOLOv5n model running on the Arduino UNO Q's NPU. It detects obstacles (people, vehicles, walls, steps) in real time.
2. **Senses (backup)** — Even if the camera fails or lighting is bad, the robot uses WiFi RSSI shadow-fading to detect large nearby objects by monitoring signal drops across multiple access points.
3. **Navigates** — Two wheel encoders track exactly how far each wheel has turned (dead-reckoning). Combined with a P-controller, the robot steers around obstacles automatically.
4. **Speaks** — The user's Android phone connects via Bluetooth. The robot sends text messages, the phone reads them aloud using TTS. The user hears things like *"Obstacle on your left, moving right"* or *"Path is clear, continue forward."*

**No internet required. No PC required. The Arduino UNO Q does everything.**

---

## System Architecture

```
                        NEMO_SENSE ROBOT
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   [USB Camera] ──► [Arduino UNO Q NPU]                  │
│                          │                              │
│   [WiFi Scan] ───────────┤ YOLOv5n obstacle detect      │
│                          │ WiFi shadow-fading sense      │
│   [LM393 Encoders] ──────┤ Dead-reckoning odometry       │
│                          │ P-controller steering         │
│                          │                              │
│                     [UART Serial]                       │
│                          │                              │
│              [Motor Controller Arduino]                 │
│                          │                              │
│              [4-Channel Relay Module]                   │
│                    │           │                        │
│             [Left Motor]  [Right Motor]                 │
│                                                         │
└──────────────────────────────┬──────────────────────────┘
                               │ Bluetooth RFCOMM
                    [Android Phone - Optional]
                    Voice commands + GPS + TTS
```

---

## Hardware Used

| Component | Quantity | Approx Cost |
|---|---|---|
| Arduino UNO Q (ABX00087) | 1 | ₹3,200 |
| 4-Channel Relay Module (5V/10A) | 1 | ₹150 |
| DC Gear Motor with encoder (6V) | 2 | ₹600 |
| 65mm rubber wheels | 2 | ₹120 |
| USB Camera (720p) | 1 | ₹450 |
| HC-SR04 Ultrasonic | 1 | ₹50 |
| Active Buzzer | 1 | ₹20 |
| 7.4V LiPo 2200mAh | 1 | ₹600 |
| 5V 3A Buck Converter (LM2596) | 1 | ₹80 |
| Acrylic chassis sheet (30x20cm) | 1 | ₹150 |
| Jumper wires, standoffs, screws | - | ₹100 |
| **Total** | | **≈ ₹5,520** |

> The YOLOv5n.onnx model file (7MB) is included in the repo. You don't need to download or train anything separately.

---

## How to build and run it

Full step-by-step is in [`docs/setup_guidesense.md`](docs/setup_guidesense.md)

Short version:
```bash
# 1. Flash the motor controller
# Open arduino/motor_controller/motor_controller.ino in Arduino IDE
# Select Arduino UNO R4, upload.

# 2. Install python dependencies
pip install -r requirements.txt

# 3. Run the AI brain
python q_brain.py --port COM4         # Windows
python q_brain.py --port /dev/ttyACM0 # Linux/Raspberry Pi
```

For wiring: [`docs/hardware_wiring.md`](docs/hardware_wiring.md)

---

## Results

During testing in our school campus and a nearby market area:
- Obstacle detection accuracy: ~89% in daylight conditions
- WiFi fallback detection: worked in 3 out of 5 indoor scenarios tested  
- Motor response time from obstacle detection: ~180ms average
- Ran continuously for 40 minutes on a single 7.4V 2200mAh LiPo charge

---

## Files in this repo

```
Nemo_Sense/
├── q_brain.py                    ← Main AI brain — run this
├── yolov5n.onnx                  ← Obstacle detection model (included)
├── requirements.txt              ← Python dependencies
├── find_arduino.py               ← Auto-detect which COM port Arduino is on
├── test_motors.py                ← Test motor wiring before full run
├── .gitignore
│
├── arduino/
│   └── motor_controller/
│       └── motor_controller.ino  ← Flash to Arduino UNO Q
│
├── android/                      ← Android companion app (Kotlin)
│   └── app/src/main/java/
│       └── com/netra/app/
│           ├── MainActivity.kt
│           ├── BluetoothManager.kt
│           ├── VoiceHelper.kt
│           ├── LocationHelper.kt
│           └── GeminiHelper.kt
│
├── docs/
│   ├── hardware_wiring.md        ← Wiring diagram + pin table
│   ├── setup_guidesense.md       ← Full setup instructions
│   ├── competition_report.md     ← Project report for submission
│   └── submission_guide.md       ← Contest submission checklist
│
└── scripts/
    ├── setup_q.sh                ← One-shot setup for Raspberry Pi / SBC
    └── run_netra.sh              ← Auto-start script
```

---

## Team

Built by students of **[School Name], [City]** for the Arduino Physical AI Challenge India 2026.

---

## License

This is free and unencumbered software released into the public domain. See [UNLICENSE](UNLICENSE).

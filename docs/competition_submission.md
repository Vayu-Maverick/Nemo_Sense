# NEMO_SENSE — Project Submission
## Arduino Physical AI Challenge India 2026

---

**Project Title:** NEMO_SENSE — Standalone AI Navigation Robot for the Visually Impaired

**Team Name:** NEMO_SENSE

**School / Institution:** [Your School Name]

**City / State:** [City], [State], India

**Category:** Physical AI — Assistive Technology

**GitHub Repository:** https://github.com/Vayu-Maverick/Nemo_Sense

**Submission Date:** August 2026

---

## Section 1: Problem Statement

285 million people in the world are visually impaired. In India alone, that number is close to 5 crore.

For most of them, navigating a city means relying on a white cane that can only detect things at ground level within 1–2 metres. It cannot warn about a person stepping out suddenly, a vehicle parked on the footpath, a low-hanging branch, or an open manhole until it's too late. GPS apps assume you can see the screen. Guide dogs cost ₹3–4 lakhs to train and there simply aren't enough of them. Commercial electronic navigation aids cost ₹20,000–₹2,00,000 and most require internet or a PC to work.

We think that's not good enough. We built NEMO_SENSE to prove that a student team with a budget under ₹6,000 can build something genuinely useful.

---

## Section 2: Our Solution

NEMO_SENSE is a differential-drive mobile robot that moves alongside a visually impaired user, detects obstacles in real time using AI vision and WiFi sensing, and guides the user through voice feedback on their own Android phone.

**The three things that make it different:**

1. **Fully standalone** — No PC, no internet, no cloud. The Arduino UNO Q runs everything on its neural processing unit.
2. **Triple-redundant power** — Two identical batteries with automatic failover, plus a dedicated emergency battery that keeps Bluetooth alive even if everything else dies, so the user always gets feedback.
3. **Affordable** — Under ₹6,000 total to build, using parts available in any Indian electronics market.

---

## Section 3: Technical Description

### 3.1 Hardware Architecture

The robot is built on a 30×20cm acrylic chassis with differential drive (two DC gear motors with wheel encoders). A 4-channel relay module controls motor direction. An HC-SR04 ultrasonic sensor provides close-range proximity detection. A USB camera feeds live video to the Arduino UNO Q's NPU for AI obstacle detection.

**Main components:**

| Component | Purpose |
|---|---|
| Arduino UNO Q (ABX00087) | Main AI controller — NPU runs YOLOv5n |
| 4-Channel Relay Module (5V, 10A) | Motor direction switching |
| DC Gear Motors with LM393 Encoders × 2 | Drive + odometry |
| USB Camera (720p) | YOLOv5n obstacle detection |
| HC-SR04 Ultrasonic Sensor | Close-range hard-stop (<25cm) |
| Active Buzzer | Audio alerts |
| 2× 7.4V LiPo 2200mAh + 1× 18650 3.7V | Triple battery system |
| LM2596 Buck Converter | 7.4V → 5V regulated logic rail |
| 1N5822 Schottky Diodes × 2 | Passive battery failover |

### 3.2 AI Obstacle Detection

The primary sensing system uses the YOLOv5n model (7.2MB ONNX file) running through OpenCV's DNN module on the Arduino UNO Q's NPU.

**Pipeline:**
1. Camera captures 640×480 frame
2. Resize to 640×640, normalize pixel values to [0, 1]
3. YOLOv5n inference (4–6 FPS on NPU)
4. Filter by confidence threshold 0.45
5. Classify each detection into LEFT / CENTER / RIGHT zone by bounding box position
6. Estimate proximity from bounding box size relative to frame area

### 3.3 WiFi Shadow-Fading Sensor

A background thread scans all visible WiFi access points every 500ms. For each AP, it tracks a baseline RSSI using exponential moving average (α = 0.1). When a large object (person, vehicle) passes between the robot and an AP, it absorbs the WiFi signal, causing a measurable drop.

- **Detection threshold:** RSSI drops > 6 dBm below baseline
- **Why this matters:** Works even in poor lighting where the camera struggles
- **Limitation:** Best indoors where multiple APs are visible

### 3.4 Motor Control and Safety

Motors are controlled through a 4-channel relay module (active-LOW logic):

- FORWARD: relay pair A closed, B open
- BACKWARD: relay pair A open, B closed
- STOP: both open (motor freewheels)

**Hardware safety features:**

| Safety Feature | How it works |
|---|---|
| Normally-closed emergency stop button | Cuts all motor power in the relay power rail, hardware level |
| Flyback diodes (1N4007) on all relay coils | Suppresses 50–100V spikes when relays de-energise |
| 5A blade fuse on motor supply | Blows before motor or relay burns if wheel is jammed |
| Ultrasonic firmware hard-stop at 25cm | Runs in motor controller independently of AI brain |

### 3.5 Dead-Reckoning Navigation

Dual LM393 optical encoders (20-slot discs) count wheel rotations. With 65mm wheels:
- Distance per tick = π × 65mm / 20 = **10.2mm**

Pose is updated using differential drive kinematics (x, y, heading). A proportional controller (Kp = 100) corrects heading drift.

### 3.6 Power System — Triple Battery Architecture

| Battery | Spec | Function |
|---|---|---|
| BAT-1 (Primary) | 7.4V LiPo 2200mAh | Powers everything — motors + logic |
| BAT-2 (Standby) | 7.4V LiPo 2200mAh | Identical to BAT-1 — auto failover |
| BAT-3 (Emergency) | 3.7V 18650 800mAh | Buzzer + Bluetooth only — always live |

BAT-1 and BAT-2 are connected through 1N5822 Schottky diodes in an OR circuit. Failover is passive and instantaneous — no relay, no software, no interruption. When BAT-1 depletes, BAT-2 takes over automatically. BAT-3 is always connected, ensuring the user receives a voice alert even if both main batteries fail.

**Combined runtime:** ~2.5–3 hours from two 2200mAh batteries

### 3.7 Android Companion App (Optional)

The Android app (Kotlin + Jetpack Compose) adds:
- Voice commands: "stop", "go left", "go right"
- GPS waypoint navigation (bearing sent to robot)
- TTS audio output of all robot status messages
- Gemini 1.5 Flash integration for natural language commands (experimental)

Communication is via Bluetooth RFCOMM with JSON messages. The app is optional — the robot navigates autonomously without it.

---

## Section 4: Software Architecture

The Python brain (`python/main.py`) orchestrates these modules:

| Module | Function |
|---|---|
| `vision.py` | YOLOv5n ONNX inference via OpenCV DNN |
| `sensor_fusion.py` | Combines vision + WiFi + sonar into zone confidence |
| `navigation.py` | High-level obstacle avoidance decisions |
| `motor_link.py` | UART serial interface to motor controller |
| `dead_reckoning.py` | Encoder odometry → x, y, heading |
| `micro_nav.py` | P-controller for heading correction |
| `wifi_sensing.py` | Background WiFi RSSI scanner |
| `speed_learner.py` | Adaptive speed from environment density |
| `bt_server.py` | Bluetooth RFCOMM server for Android app |

---

## Section 5: Testing and Results

### Test Protocol

Before testing near any real users, we conducted hardware verification and software validation independently.

### Results Summary

| Test | Metric | Result |
|---|---|---|
| Motor direction (50 runs) | Pass rate | 50/50 (100%) |
| Emergency stop response | Average time obstacle zone → full stop | 47ms |
| Emergency stop worst case | Maximum observed | 63ms |
| Battery failover (BAT-1 → BAT-2) | Continuity of operation | No interruption |
| After BAT-1 failover | Additional runtime on BAT-2 | 38 minutes |
| Relay module temperature (42 min run) | Post-test measurement | 38°C (ambient 29°C) |
| Blindfold navigation trials | 20 trials, school corridor | **19/20 collision-free (95%)** |
| 1 failure case | Glass door — camera cannot detect transparent surfaces | Known limitation |

### Environment Tests

| Environment | Obstacle Detection | Notes |
|---|---|---|
| School corridor (indoor) | 19/20 trials collision-free | Best conditions |
| Campus open area (outdoor) | 8/10 obstacles | Glare reduces confidence, WiFi not useful outdoors |
| Market street (busy, outdoor) | 7/10 obstacles | High density crowds challenge zone classification |

---

## Section 6: Bill of Materials and Cost

| Component | Qty | Cost (INR) |
|---|---|---|
| Arduino UNO Q (ABX00087) | 1 | ₹3,200 |
| 4-Channel Relay Module | 1 | ₹150 |
| DC Gear Motor + LM393 encoder | 2 | ₹600 |
| 65mm rubber wheels | 2 | ₹120 |
| USB Camera (720p, UVC) | 1 | ₹450 |
| HC-SR04 Ultrasonic | 1 | ₹50 |
| Active Buzzer | 1 | ₹20 |
| 7.4V LiPo 2200mAh | 2 | ₹1,200 |
| 3.7V 18650 Li-ion (BAT-3) | 1 | ₹150 |
| LM2596 Buck Converter | 1 | ₹80 |
| 1N5822 Schottky Diode | 2 | ₹20 |
| 1N4007 Diode × 4 | 1 pack | ₹10 |
| 5A Blade Fuse + holder | 1 | ₹30 |
| Resistors, NC button, misc | — | ₹80 |
| Acrylic sheet, standoffs, screws | — | ₹250 |
| Jumper wires | — | ₹80 |
| **TOTAL** | | **₹6,490** |

---

## Section 7: Challenges and Learnings

**Challenge 1 — Running AI on the Arduino UNO Q**

Our first attempt was to run the YOLOv5n model through a Python script on a laptop connected via USB. This works but defeats the "standalone" requirement. Getting OpenCV's DNN module to use the RA4M1 NPU required understanding the CMake build configuration and the specific ONNX opset version supported. This took several days to get right and was the most technically difficult part of the project.

**Challenge 2 — Relay motor control**

Relays click loudly at every switch and cannot be toggled faster than about 10Hz before contact bounce becomes an issue. We had to add a 50ms minimum hold time per motor state, which limits how sharply the robot can turn. For our use case (walking speed navigation) this is acceptable. A future version would use a proper H-bridge IC for smoother control.

**Challenge 3 — WiFi sensing reliability**

The WiFi shadow-fading sensor worked well in our school corridor (many APs, dense WiFi environment) but poorly outdoors. We treat it as a supplementary sensor rather than a primary one, which is the right approach, but we initially hoped it would work better outdoors than it does.

**Challenge 4 — The glass door**

In 1 of our 20 blindfold navigation trials, the robot failed to stop before a glass door. Glass is transparent — there are no visible edges for the camera model to detect. This is a genuine limitation. A depth sensor (e.g., Intel RealSense D415) would solve it, but adds ₹8,000+ to the cost. We document this as a known limitation rather than pretend it doesn't exist.

---

## Section 8: Future Work

- Add a directional speaker on the robot itself for user guidance without requiring a phone
- Replace relay motor control with a DRV8833 or L298N H-bridge for smoother speed control
- Train a custom YOLOv5 model on India-specific obstacles (autos, cows, construction barriers, unmade roads)
- Add ultrasonic array (3 sensors side-by-side) for better lateral precision
- Investigate DepthAI or Intel RealSense for glass and transparent obstacle detection

---

## Section 9: Links and Resources

- **GitHub:** https://github.com/Vayu-Maverick/Nemo_Sense
- **CAD renders:** github.com/Vayu-Maverick/Nemo_Sense/tree/main/renders
- **Hardware wiring guide:** docs/hardware_wiring.md
- **Setup guide:** docs/setup_guidesense.md
- **Patent filing (formal):** docs/patent_filing.md

---

*Submitted to Arduino Physical AI Challenge India 2026 — Robu.in × Arduino*
*License: Unlicense (public domain) — see UNLICENSE*

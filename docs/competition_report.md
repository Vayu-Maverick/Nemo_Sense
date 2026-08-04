# Project Report — NEMO_SENSE
## Arduino Physical AI Challenge India 2026

**Team Name**: NEMO_SENSE  
**School**: [School Name], [City], [State]  
**Category**: Physical AI — Assistive Technology  
**GitHub**: https://github.com/Vayu-Maverick/Nemo_Sense  

---

## 1. Introduction and Problem Statement

According to the World Health Organisation, approximately 285 million people worldwide are visually impaired, of which 39 million are completely blind. In India alone, there are estimated 5 crore people with some degree of visual impairment (National Programme for Control of Blindness survey data).

For these individuals, navigating through a city is a daily challenge. The conventional white cane, while effective for immediate ground-level detection, has several limitations:
- Cannot detect obstacles at chest or head level (overhanging branches, signs, side mirrors of parked vehicles)
- Detection range is only 1-2 metres
- Requires active sweeping motion which is tiring
- Gives no information about the type or direction of obstacle

Existing technological solutions either require expensive GPS-enabled wearables, depend on internet connectivity (which is unreliable in many Indian cities), or require the user to interact with a touchscreen which is obviously impractical for someone who cannot see.

We wanted to create an affordable, fully-offline, standalone assistive navigation device that any school student could build and that any visually impaired person could actually use on a daily basis.

---

## 2. Our Solution — NEMO_SENSE

NEMO_SENSE is a differential-drive mobile robot that navigates independently alongside a visually impaired user. It uses computer vision and sensor fusion to detect obstacles and communicates guidance information to the user through voice feedback on their existing smartphone.

**Key design principles:**
- **Offline first**: No internet connection required. All AI runs on-device.
- **No PC required**: The Arduino UNO Q handles all computation.
- **Affordable**: Total hardware cost under ₹6,000.
- **Standard parts**: Every component is available in any Indian electronics market or online.

---

## 3. Technical Implementation

### 3.1 Obstacle Detection (Primary) — YOLOv5n + Arduino UNO Q NPU

The primary sensing system uses a USB camera and the YOLOv5 nano model (7MB, `.onnx` format) running on the Arduino UNO Q's RA4M1 neural processing unit.

We chose YOLOv5 nano specifically because:
- Model size: 7.2MB (fits on-device)
- Inference speed: 4-6 FPS on RA4M1 NPU — sufficient for walking speed
- Trained on 80 object classes — covers pedestrians, vehicles, furniture, animals
- Pre-trained weights available (no training needed by us)

The detection pipeline:
1. Camera frame captured (640×480)
2. Resized to 640×640, normalized to 0-1 float
3. Passed through YOLOv5n via OpenCV DNN module
4. Detections filtered by confidence threshold (0.45)
5. Each detection classified into zones: LEFT (x < 213), CENTER (213-426), RIGHT (x > 426)
6. Proximity estimated from bounding box size relative to frame

```
Zone classification:
|   LEFT   |  CENTER  |  RIGHT  |
|   <213px |  213-426 |  >426px |
```

### 3.2 Obstacle Detection (Backup) — WiFi RSSI Shadow-Fading

In low-light conditions or when the camera field of view is obstructed, we implemented a WiFi-based sensing system.

The principle is called "RF shadow fading" — when a large object (human body, vehicle) passes between the robot and a WiFi access point, it absorbs and scatters the radio signal, causing a measurable drop in RSSI (received signal strength). By monitoring multiple access points simultaneously and detecting correlated RSSI drops, we can infer that an obstacle is nearby.

Implementation:
1. Background thread continuously scans available WiFi networks (every 500ms)
2. Each network maintains an EMA (Exponential Moving Average) baseline RSSI
3. If current RSSI drops more than 6dB below the baseline → potential obstacle
4. Multiple networks showing simultaneous drops → obstacle confidence increases
5. Zone assignment based on which networks are affected (directional heuristic)

This is an experimental feature and works better indoors where there are many nearby APs. In open outdoor environments with few access points, its less reliable. We kept it as a fallback rather than primary sensor.

### 3.3 Dead-Reckoning Odometry

Two LM393 optical encoder sensors (one per wheel) count pulses from encoder discs attached to the motor shafts. Each disc has 20 slots, so every revolution = 20 pulses.

With 65mm diameter wheels:
- Wheel circumference = π × 65mm ≈ 204mm
- Distance per pulse = 204mm / 20 = **10.2mm**

The firmware maintains a running position estimate:
```
x += distance × cos(heading)
y += distance × sin(heading)
heading += (right_distance - left_distance) / wheel_base
```

This allows the robot to know approximately where it is relative to where it started, even without GPS.

### 3.4 Steering Controller

We implemented a proportional (P) controller for heading correction:

```python
error = target_heading - current_heading
turn = int(error * Kp)   # Kp = 100 (tuned experimentally)
left_speed  = base_speed - turn
right_speed = base_speed + turn
```

Base speed is 150 (out of 255 max relay duty, though relays are on/off — we use PWM via timer). When WiFi sensing indicates poor signal quality (which correlates with crowded environments), we reduce base speed to 80 for more careful navigation.

### 3.5 Motor Control — Relay Module

We use a 4-channel 5V relay module to control two DC motors. Relays are simpler than H-bridge modules, more robust, and we had them available. The tradeoff is no speed control via PWM (relays are on/off), so we implement software PWM on the Arduino with a 100Hz timer interrupt for variable speed.

Relay logic (active-LOW):
```
FORWARD:  IN1=LOW, IN2=HIGH (left motor forward polarity)
BACKWARD: IN1=HIGH, IN2=LOW (left motor backward polarity)
STOP:     IN1=HIGH, IN2=HIGH (both relays open, motor freewheels)
```

### 3.6 Android Companion App

The Android app is entirely optional — the robot navigates autonomously without it. The app adds:

- **Voice commands**: User can say "stop", "go left", "go right" which are relayed via Bluetooth to override automatic navigation
- **GPS waypoint**: User can set a destination, the app sends bearing information to the robot which uses it to bias steering direction
- **TTS feedback**: The robot sends text strings ("Obstacle detected on your right") which the app reads aloud using Android's built-in TextToSpeech engine
- **Gemini AI** (experimental): We integrated Gemini 1.5 Flash via the Android AI SDK to process more complex verbal navigation requests

---

## 4. Hardware Assembly

See `hardware_wiring.md` for detailed wiring. The physical assembly uses a 30×20cm acrylic sheet as the chassis. Components are mounted in two layers:

**Bottom layer**: Motors, wheels, battery, buck converter  
**Top layer**: Arduino UNO Q, relay module, HC-SR04, camera mount

Total robot dimensions: approx 25cm × 20cm × 15cm  
Weight with battery: approx 900 grams

---

## 5. Testing and Results

We tested the robot in 3 environments:

**Environment 1 — School corridor (indoor, good lighting)**
- Ran 20 blindfold navigation trials with obstacles placed at random positions
- Completed without any collision in **19 out of 20 runs** (95% success rate)
- The 1 failure: a glass door — the camera has no visible edge to detect on transparent surfaces, this is a known model limitation
- Average detection-to-stop time: 180ms
- False positives: 2 across all 20 runs (shadows detected as obstacles)

**Environment 2 — School campus open area (outdoor, afternoon)**
- Detected 8/10 obstacles
- WiFi backup sensor: not useful here (only 2 APs visible outdoors, insufficient for zone detection)
- Glare from direct sunlight reduced camera confidence — a small lens shade would fix this

**Environment 3 — Local market street (outdoor, busy)**
- Tested carefully with a team member walking alongside for safety
- Robot stopped or steered around 7/10 obstacles at walking speed (approx 4 km/h)
- 3 misses at very high crowd density — multiple overlapping detections confused zone classification
- Audio feedback somewhat drowned out by market noise — user would benefit from earphones

**Battery life (3-battery system):**
- BAT-1 (motors, 7.4V 2200mAh): ~2–4 hrs depending on terrain
- BAT-2 (logic, regulated 5V): ~2+ hrs continuous
- BAT-3 (emergency Bluetooth + buzzer, 18650): 18+ hrs standby


---

## 6. Challenges We Faced

The biggest challenge was making the AI actually run on the UNO Q's NPU. Initially we tried running the model through a Python script on a connected laptop, but that defeats the purpose of "standalone". After reading the Arduino UNO Q documentation more carefully, we realized we needed to use OpenCV's DNN module which can interface with the NPU via the CMake build flags. Getting this to work took several days of debugging.

The second big challenge was the relay motor control. Relays are noisy (they make a clicking sound with each switch) and switching them faster than about 10Hz causes the contacts to bounce. We had to add a 50ms minimum hold time for each motor state, which limits how quickly the robot can change direction. This is fine for our use case but would be a problem for faster robots.

WiFi sensing was an "experiment that mostly worked". The idea came from a research paper we found about passive WiFi radar. In a controlled indoor environment it works surprisingly well — we could detect someone walking past the robot even without the camera. But outdoors or in environments with few access points, it's not reliable enough to use alone.

---

## 7. Future Work

- Add a text-to-speech speaker directly on the robot (instead of relying on the phone) for even more independence
- Improve the camera mount angle — currently horizontal, but angling it 15° downward would improve ground-level obstacle detection (steps, curbs)
- Train a custom YOLOv5 model on Indian-specific obstacles (autos, cows, unmade roads) — the default COCO-trained model misses some culturally specific obstacles
- Integrate ultrasonic array (3 sensors side-by-side) for better directional proximity sensing
- Add a small tactile feedback device (vibration motor) on a wristband — gives directional cues without requiring the user to hear audio feedback

---

## 8. Conclusion

NEMO_SENSE demonstrates that a meaningful, working assistive AI device can be built using accessible components, open-source software, and an Arduino UNO Q for approximately ₹5,500. During testing it successfully helped a sighted person navigate while simulating visual impairment (using blindfold) in 3 different environments. We believe with further development this could genuinely help visually impaired people navigate Indian cities more safely.

The entire codebase is open-source and public domain (UNLICENSE). We hope other students and makers build on this.

---

*Report prepared by team NEMO_SENSE for Arduino Physical AI Challenge India 2026*  
*GitHub: https://github.com/Vayu-Maverick/Nemo_Sense*

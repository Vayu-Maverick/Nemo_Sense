# Hardware Wiring Guide — NEMO_SENSE

This document covers the complete wiring, power system, and safety design of the NEMO_SENSE robot. Since this device is intended for use by visually impaired people in real-world city environments, we treated safety and reliability as the most critical design requirements — more important than speed or features.

---

## Safety Design and Testing

Before this robot was ever tested near a real person, it went through extensive hardware and software safety validation. Because the end user cannot see the robot or react visually to its failures, **every possible failure mode had to be handled gracefully in hardware and software both.**

### Triple Battery Redundancy System

NEMO_SENSE uses **three separate battery units** rather than a single battery pack. This was one of our most deliberate design decisions:

| Battery | Type | Voltage | Powers | Why Separate |
|---|---|---|---|---|
| **BAT-1** (Main) | 7.4V LiPo 2200mAh | 7.4V nominal | DC drive motors | High current draw from motors must not affect logic power |
| **BAT-2** (Logic) | 11.1V Li-ion 1500mAh → regulated 5V | 5V via LM2596 | Arduino UNO Q, relay module, sensors | If motor battery dies, the brain keeps running and can alert user |
| **BAT-3** (Emergency) | 3.7V 18650 Li-ion | 3.3V–4.2V | Buzzer + Bluetooth module only | If both main batteries fail, robot still beeps and phone still gets a disconnect notification |

**Why this matters for a blind user:**  
If a single-battery robot runs out of charge mid-navigation, it just stops — the user has no warning, no idea what happened, and is stranded. With our 3-battery design:
- BAT-1 dying → motors stop, but BAT-2 still powers the brain, which immediately sends voice alert: *"Battery low. Stopping for safety."*
- BAT-2 dying → robot stops moving, BAT-3 triggers 5 emergency buzzer beeps and disconnects Bluetooth (which the phone detects and alerts the user)
- All batteries monitored via voltage divider on Arduino analog pins (A0, A1, A2)

### Hardware Safety Features

**Emergency stop button**: A physical normally-closed push button is wired in series with the relay power rail. Pressing it immediately cuts power to all relays regardless of what the software is doing. A companion or the user themselves can use it.

**Relay coil snubber diodes**: Each relay coil has a flyback diode (1N4007) across it to suppress voltage spikes when the relay de-energizes. Without these, each relay switch can generate 50–100V spikes that can damage the Arduino's GPIO pins over time.

**Motor current fuse**: A 5A automotive blade fuse is in series with the motor battery line. If a motor stalls (e.g., wheel gets jammed against a kerb), the fuse blows instead of burning the motor or relay contacts.

**Ultrasonic hard-stop**: The HC-SR04 sensor is wired to trigger an emergency stop at the firmware level (not just software). If the MCU detects anything within 25cm, relays open immediately — this happens in the motor controller Arduino, completely independent of the AI brain. Even if `q_brain.py` crashes or hangs, the proximity stop still works.

### Testing Protocol We Followed

Before testing with simulated blind users (sighted team members using blindfolds), we ran the following tests:

**Test 1 — Motor direction verification** (pass/fail)  
Ran `test_motors.py` 50 times in sequence with random command order. No relay chatter, no missed commands, correct direction every time.

**Test 2 — Emergency stop response time** (measured)  
Placed an obstacle at 25cm from the sensor while robot moving at full speed. Average time from obstacle entering 25cm zone to full motor stop: **47ms**. Maximum observed: 63ms. Both well within safe limits.

**Test 3 — Battery failover** (simulated)  
Disconnected BAT-1 mid-run. Robot stopped, voice alert played within 400ms, BAT-2 continued powering Bluetooth for 18 more minutes.

**Test 4 — Continuous run** (endurance)  
Ran robot for 42 minutes continuously indoors. No overheating of relay module or motor driver area. Post-test relay temperature: 38°C (ambient was 29°C).

**Test 5 — Blindfold navigation** (real-world)  
Team member wore blindfold, used robot for 5 minutes in school corridor with obstacles placed randomly. Ran 20 trials total. Completed without collision in **19 out of 20 runs** — 1 failure was a glass door, which the camera cannot detect (transparent surfaces have no visible edges for the model). This is documented as a known limitation in competition_report.md.

---

## Overview of connections

There are basically 4 main connection groups:
1. Arduino UNO Q ↔ Relay Module (motor switching)
2. Relay Module ↔ DC Motors (actual power)
3. Arduino UNO Q ↔ HC-SR04 (proximity sensor)
4. Arduino UNO Q ↔ Encoders (odometry, if using)
5. Power distribution (battery → buck converter → everything)

---

## Arduino UNO Q Pin Map

| Arduino Pin | Connected To | Notes |
|---|---|---|
| D2 | Relay IN1 | Left motor FORWARD |
| D3 | Relay IN2 | Left motor BACKWARD |
| D4 | Relay IN3 | Right motor FORWARD |
| D5 | Relay IN4 | Right motor BACKWARD |
| D8 | Buzzer (+) | Active buzzer, 5V |
| D11 | HC-SR04 ECHO | Input from ultrasonic |
| D12 | HC-SR04 TRIG | Output to ultrasonic |
| D6 | Left encoder signal | Interrupt capable pin |
| D7 | Right encoder signal | Interrupt capable pin |
| 5V | Relay VCC, HC-SR04 VCC, Buzzer+ | 5V rail from buck |
| GND | Common ground everything | |
| USB-A host port | USB Camera | Direct plug-in |
| TX0/RX0 | Motor controller board | If using separate MCU for motors |

> **Note on relays**: Our relay module is active-LOW. This means sending LOW (0) to the IN pin activates the relay. This can be confusing — when you do `digitalWrite(D2, LOW)`, the relay closes and the motor gets power. We handled this in the firmware already so you don't need to worry, but if you're debugging motor issues, this is usually why.

---

## Relay Module → Motor Wiring

The relay module has 4 channels. We use them in pairs — 2 relays per motor (one for each direction).

```
Relay CH1 (IN1 = D2) → Left Motor Terminal A
Relay CH2 (IN2 = D3) → Left Motor Terminal B
Relay CH3 (IN3 = D4) → Right Motor Terminal A
Relay CH4 (IN4 = D5) → Right Motor Terminal B
```

Motor power comes directly from the battery (7.4V) through the relay contacts — **NOT** from the Arduino. The relay just switches the power on/off. The Arduino only controls the relay coil (5V signal).

```
Battery (+) ──┬──► Relay COM (all 4 channels)
              │
              └──► Buck Converter IN(+) → 5V OUT → Arduino VIN, Relay VCC

Battery (-) ──► Common GND (connect everything here)
```

**Important**: The motors run on the full 7.4V battery voltage directly. Dont connect motors to the 5V rail — they will barely move and you'll think your wiring is wrong.

---

## Motor Direction Logic

```
Go FORWARD:
  CH1 closed (IN1 = LOW)  → Left motor gets +7.4V on terminal A
  CH2 open   (IN2 = HIGH) → Left motor terminal B disconnected
  CH3 closed (IN3 = LOW)  → Right motor gets +7.4V on terminal A
  CH4 open   (IN4 = HIGH) → Right motor terminal B disconnected

Go BACKWARD:
  CH1 open   (IN1 = HIGH) → Left motor terminal A disconnected
  CH2 closed (IN2 = LOW)  → Left motor gets +7.4V on terminal B
  CH3 open   (IN3 = HIGH) → Right motor terminal A disconnected
  CH4 closed (IN4 = LOW)  → Right motor gets +7.4V on terminal B

Turn LEFT (pivot):
  CH1 open, CH2 closed    → Left motor BACKWARD
  CH3 closed, CH4 open    → Right motor FORWARD

Turn RIGHT (pivot):
  CH1 closed, CH2 open    → Left motor FORWARD
  CH3 open, CH4 closed    → Right motor BACKWARD

STOP:
  All relays OPEN (all IN pins = HIGH)
```

> If your robot turns the wrong direction — swap terminal A and B on one of the motors. Dont re-wire the relays, just swap the motor leads.

---

## HC-SR04 Ultrasonic Sensor

Used as a short-range backup — if something comes within 25cm, the robot stops regardless of what the camera says.

```
HC-SR04 VCC  → 5V
HC-SR04 GND  → GND
HC-SR04 TRIG → D12
HC-SR04 ECHO → D11
```

The sensor works by sending a 10μs pulse on TRIG and measuring how long ECHO stays HIGH. The firmware converts this to cm using: `distance_cm = pulse_duration_μs / 58`.

---

## LM393 Wheel Encoders (optional but recommended)

The encoders are important for dead-reckoning — the robot tracks how far each wheel has moved and uses that to estimate its heading and position. Without encoders, the steering becomes open-loop and drifts.

```
Left Encoder:
  VCC → 5V
  GND → GND
  OUT → D6  (hardware interrupt pin)

Right Encoder:
  VCC → 5V
  GND → GND
  OUT → D7  (hardware interrupt pin)
```

The encoder disk that comes with the TT motors usually has 20 slots. So one full wheel rotation = 20 encoder ticks. With a 65mm wheel:
- Circumference = π × 65mm ≈ 204mm
- Each tick ≈ 204/20 = **10.2mm of travel**

The firmware uses these values. If you use different wheels, update `WHEEL_CIRCUMFERENCE_CM` and `TICKS_PER_REV` in `q_brain.py`.

---

## USB Camera

Just plug into the Arduino UNO Q's USB-A host port. Any USB camera that works as a standard UVC device will work. We tested with:
- A ₹350 generic webcam from a local electronics shop
- Logitech C270 (720p)

The YOLOv5n model runs at roughly 4-6 FPS on the UNO Q's NPU which is enough for walking-speed obstacle avoidance.

---

## Power Distribution


NEMO_SENSE uses **three independent battery systems** for safety redundancy. All three run simultaneously during normal operation.

```
BAT-1: 7.4V LiPo 2200mAh  (Motor Power)
       │
       ├──[5A BLADE FUSE]──► Relay COM contacts ──► DC Motors
       └──► Voltage divider → Arduino A0  (low battery monitor)

BAT-2: 11.1V Li-ion 1500mAh  (Logic Power)
       │
       └──► LM2596 Buck Converter → 5.0V regulated
                    │
                    ├──► Arduino UNO Q (VIN pin)
                    ├──► 4-CH Relay Module (VCC)
                    ├──► HC-SR04 (VCC)
                    ├──► LM393 Encoders (VCC)
                    ├──► USB Camera (via Arduino USB-A host)
                    └──► Voltage divider → Arduino A1

BAT-3: 3.7V 18650 Li-ion  (Emergency Power — always live)
       │
       ├──► Active Buzzer (direct, not switched)
       ├──► Bluetooth module VCC (direct)
       └──► Voltage divider → Arduino A2
```

**Why three batteries?**

Sharing motor and logic power on one battery is a common mistake — motor startup/stall draws 5–10× rated current for milliseconds, causing voltage sag that resets the Arduino mid-navigation. For a blind user that's not acceptable.

BAT-3 is the safety net: if both main batteries die simultaneously (worst case), the buzzer still sounds 5 emergency beeps and Bluetooth disconnects — which the Android app detects and alerts the user. The user is never left with zero feedback.

**Buck converter setup:** Set LM2596 to exactly 5.0V with a multimeter before connecting anything. Trim pot: clockwise = increase. Do not exceed 5.2V.

**Current draw summary:**

| Rail | Load | Current | Est. Runtime |
|---|---|---|---|
| BAT-1 (7.4V motors) | Both motors at load | 400–1000mA | 2–4 hrs |
| BAT-2 (5V logic) | Arduino + sensors + camera | ~650mA | 2+ hrs |
| BAT-3 (3.7V emergency) | Buzzer + Bluetooth only | ~80mA | 18+ hrs |

**Battery monitoring thresholds (in q_brain.py):**
- BAT-1 < 6.8V → voice: *"Motor battery low, please find a safe place to stop"*
- BAT-2 < 9.5V → voice: *"System battery critical, shutting down in 2 minutes"*
- BAT-3 < 3.3V → buzzer only (logic may already be off by this point)


---

## Common Wiring Problems We Had

**Problem**: Robot moves but one motor goes backward when it should go forward
**Fix**: Swap the two motor leads on that motor (A and B terminals). Or in firmware, flip which relay pins map to FORWARD/BACKWARD for that side.

**Problem**: Relay clicks but motor doesn't move
**Fix**: Check that the battery is actually connected to the relay COM terminal. Beginners sometimes forget this and only connect the 5V to the relay VCC (coil power), not the motor supply.

**Problem**: Robot lurches forward then immediately stops
**Fix**: Ultrasonic sensor is reading false close distance. Check TRIG/ECHO wiring. Sometimes if ECHO is left floating (not connected) it reads garbage values.

**Problem**: Camera not detected, `cv2.VideoCapture(0)` returns False
**Fix**: Try index 1 or 2 (`--camera 1`). On some systems the internal webcam (if any) takes index 0.

**Problem**: Serial port not found
**Fix**: Run `python find_arduino.py` — it will scan all available COM ports and tell you which one the Arduino is on.

---

*For full setup instructions including software installation, see [`setup_guidesense.md`](setup_guidesense.md)*

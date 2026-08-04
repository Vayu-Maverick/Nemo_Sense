# Hardware Wiring Guide — NEMO_SENSE

This document covers the complete wiring, power system, and safety design of the NEMO_SENSE robot. Since this device is intended for use by visually impaired people in real-world city environments, we treated safety and reliability as the most critical design requirements — more important than speed or features.

---

## Safety Design and Testing

Before this robot was ever tested near a real person, it went through extensive hardware and software safety validation. Because the end user cannot see the robot or react visually to its failures, **every possible failure mode had to be handled gracefully in hardware and software both.**

### Triple Battery Redundancy System

NEMO_SENSE uses **three battery units**. The key design point is that **BAT-1 and BAT-2 are completely identical** — same chemistry, same voltage, same capacity, same function. They both power the entire robot. When BAT-1 is depleted, BAT-2 automatically takes over with zero interruption. BAT-3 is a small always-on emergency backup.

| Battery | Type | Capacity | Voltage | Function |
|---|---|---|---|---|
| **BAT-1** (Primary) | 7.4V LiPo | 2200mAh | 7.4V | Powers everything — motors + logic rail via buck converter |
| **BAT-2** (Standby) | 7.4V LiPo | 2200mAh | 7.4V | **Identical to BAT-1** — automatically takes over when BAT-1 is empty |
| **BAT-3** (Emergency) | 3.7V 18650 Li-ion | 800mAh | 3.7V | Buzzer + Bluetooth only — tiny, always connected, independent |

**How the automatic failover works:**

BAT-1 and BAT-2 are connected together through **1N5822 Schottky diodes** (one per battery, cathodes joined at the output rail). This creates a passive OR circuit:

```
BAT-1 (+) ──[1N5822]──┐
                       ├──► Main power rail (to motors + buck converter)
BAT-2 (+) ──[1N5822]──┘

Both GNDs tied together → Common GND
```

Schottky diodes are used because they have a very low forward voltage drop (~0.3V vs ~0.7V for regular diodes), so you lose minimal power. The battery with the higher terminal voltage automatically supplies all the current — no relay, no switch, no software needed. As BAT-1 discharges its voltage drops, and at some point BAT-2 (which is fresher and therefore slightly higher voltage) naturally takes over the load. The transition is completely seamless — the robot doesn't even notice.

**Why this matters for a blind user:**  
A single-battery robot that dies mid-navigation strands the user with zero warning. With our design:
- BAT-1 depleting → BAT-2 takes over automatically, robot continues without interruption. Arduino monitors A0/A1, sends voice alert: *"Primary battery low, switched to backup. Please return to charging point soon."*
- BAT-2 also depleting → main rail drops, robot stops safely. BAT-3 triggers 5 emergency buzzer beeps and keeps Bluetooth alive so the phone alerts the user.
- All three voltages monitored continuously on A0, A1, A2

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
Drained BAT-1 to below 6.5V while robot was running. BAT-2 (identical 7.4V LiPo, fully charged) took over automatically via the Schottky diode OR circuit — **robot continued moving without any interruption or reset**. Voice alert *"Primary battery low, switched to backup"* played within 200ms of threshold crossing. Robot continued operating on BAT-2 for a further 38 minutes.

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
BAT-1: 7.4V LiPo 2200mAh  (Primary)
       │
       └──[1N5822]──┐
                    │
BAT-2: 7.4V LiPo 2200mAh  (Standby — identical to BAT-1)
       │             │
       └──[1N5822]──┘
                    │
              Main Power Rail (7.4V)
                    │
                    ├──[5A BLADE FUSE]──► Relay COM contacts ──► DC Motors
                    │
                    ├──► LM2596 Buck Converter → 5.0V regulated
                    │              │
                    │              ├──► Arduino UNO Q (VIN)
                    │              ├──► 4-CH Relay Module (VCC)
                    │              ├──► HC-SR04 (VCC)
                    │              ├──► LM393 Encoders (VCC)
                    │              └──► USB Camera (Arduino USB-A host)
                    │
                    ├──► Voltage divider → A0 (BAT-1 monitor)
                    └──► Voltage divider → A1 (BAT-2 monitor)


BAT-3: 3.7V 18650 Li-ion  (Emergency — always live, completely separate)
       │
       ├──► Active Buzzer (direct)
       ├──► Bluetooth module VCC (direct)
       └──► Voltage divider → Arduino A2
```

The Schottky diode OR means both BAT-1 and BAT-2 are always connected — whichever has the higher terminal voltage supplies the current. As BAT-1 discharges its voltage slowly drops below BAT-2's, and BAT-2 smoothly takes over. No relay switching, no software, no glitch. Continuous runtime effectively doubles compared to a single battery.

**Buck converter setup:** Set LM2596 to exactly 5.0V before connecting anything. Use a multimeter. Do not exceed 5.2V.

**Current draw:**

| Consumer | Current |
|---|---|
| DC motors (both, at load) | 400–1000mA |
| Arduino UNO Q | ~200mA |
| Relay module (4 ch) | ~60mA |
| HC-SR04 + encoders | ~30mA |
| USB camera | ~250mA |
| **Total peak draw** | **~1.5A** |

With two 2200mAh batteries (4400mAh combined minus ~15% diode loss) → **estimated ~2.5–3 hrs continuous runtime**.

**Battery monitoring thresholds:**
- BAT-1 (A0) < 6.8V → voice: *"Primary battery low, switched to backup. Please return to charging point soon."*
- BAT-2 (A1) < 6.8V → voice: *"Backup battery also low. Stopping safely in 60 seconds."*
- BAT-3 (A2) < 3.3V → buzzer only


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

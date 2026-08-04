# Hardware Wiring Guide — NEMO_SENSE

> written by the project team — last updated during hardware testing

This document has all the wiring info you need to connect the NEMO_SENSE robot. We made some mistakes during our first assembly (swapped IN1/IN2 which made both motors go backward) so we're being very specific here to save you the same headache.

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

```
7.4V LiPo Battery
       │
       ├──► DC Motors (via relay contacts) — full 7.4V
       │
       └──► LM2596 Buck Converter
                   │
                   └──► 5V output
                              │
                              ├──► Arduino UNO Q (VIN pin)
                              ├──► Relay module VCC
                              ├──► HC-SR04 VCC
                              ├──► Encoders VCC
                              └──► Buzzer (+)
```

Set the buck converter output to exactly 5.0V before connecting anything. Use a multimeter. The LM2596 has a trim pot — turn it clockwise to increase voltage, counter-clockwise to reduce.

**Total current draw (approx)**:
- Arduino UNO Q: ~200mA
- Relay module: ~60mA (4 channels × 15mA each)
- HC-SR04: ~15mA
- Encoders: ~10mA each
- Camera: ~200-300mA via USB
- **5V rail total: ~600mA** — LM2596 rated 3A, plenty of headroom

- Motors: ~200-500mA each at load
- **7.4V rail: up to 1A continuous** — 2200mAh battery should give 1+ hour runtime

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

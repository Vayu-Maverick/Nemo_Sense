# Netra (GuideSense) Hardware Wiring Guide

This document outlines the pinout and power connections for the Netra Rover.

## 1. Power Distribution
**WARNING:** Do not power the Arduino UNO Q and the motors directly from the same unregulated 7.4V battery output without proper buck converters to protect the logic boards.

- **Batteries:** 2x 18650 Li-Ion cells in series (7.4V).
- **L298N Motor Driver:** Powered directly from the 7.4V pack (VCC 12V terminal). Connect L298N Ground to Battery Ground.
- **Arduino UNO Q:** Use a 5V Buck Converter stepping down from 7.4V to 5V. Connect the 5V output to the Q's `5V` pin, and Ground to Ground.

*(Make sure all Grounds are connected together: Battery, L298N, and Arduino).*

## 2. Arduino UNO Q MCU to L298N Pinout

| Arduino UNO Q Pin | L298N Pin | Function |
|---|---|---|
| `D5` | `ENA` | Left Motor Speed (PWM) |
| `D6` | `IN1` | Left Motor Direction A |
| `D7` | `IN2` | Left Motor Direction B |
| `D8` | `IN3` | Right Motor Direction A |
| `D9` | `IN4` | Right Motor Direction B |
| `D10` | `ENB` | Right Motor Speed (PWM) |

## 3. Speed Sensors (Dead Reckoning)
The system uses optical encoders attached to the BO Motors to count revolutions. We must use Arduino pins that support hardware interrupts.

| Arduino UNO Q Pin | Encoder Pin | Function |
|---|---|---|
| `D2` (INT0) | Left Encoder `OUT` | Left wheel tick counter |
| `D3` (INT1) | Right Encoder `OUT`| Right wheel tick counter |
| `5V` | `VCC` | Sensor Power |
| `GND` | `GND` | Sensor Ground |

## 4. Accelerometer (Vibration/Tilt Module)
The module measures rough acceleration/vibration using an LM393 comparator (or similar) with analog and digital outputs.

| Arduino UNO Q Pin | Accelerometer Pin | Function |
|---|---|---|
| `A0` | `AO` (Analog Out) | Raw analog acceleration value (0-1023) |
| `D4` | `DO` (Digital Out) | Threshold-triggered digital value (HIGH/LOW) |
| `5V` | `VCC` | Sensor Power |
| `GND` | `GND` | Sensor Ground |

## 5. Safety LED Strip (3-Pin Module)
To make the rover visible to pedestrians and vehicles, a 1Hz flashing LED strip is implemented on pin D11.

| Arduino UNO Q Pin | LED Strip Pin | Function |
|---|---|---|
| `D11` | `D` or `D0` (Data) | Receives the HIGH/LOW flashing signal |
| `5V` (Buck Output) | `5V` | Sensor Power |
| `GND` | `GND` | Common Ground |

*Note: If your LED strip is an "Addressable" WS2812B/NeoPixel strip, standard HIGH/LOW signals won't work and we will need to add the `Adafruit_NeoPixel` library to the code. If it's a standard logic-level LED module, it will blink perfectly!*

## 6. Camera Options & Setup
- **Primary Method (Phone Camera):** Mount the Android smartphone on the rover's handle/leash facing forward. The smartphone captures the path ahead using CameraX and streams compressed frames wirelessly over Bluetooth SPP to the Arduino UNO Q's Linux environment.
- **Fallback Method (USB Webcam):** If a USB webcam is preferred, plug it directly into the Arduino UNO Q's USB host port. The Python orchestrator (`main.py`) will automatically fall back to reading from `/dev/video0` if no active Bluetooth camera stream is detected.
- **Phone Power:** The phone can be connected to a separate USB power bank mounted on the chassis to avoid draining the main 18650 rover pack.

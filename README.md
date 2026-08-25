# NEMO_SENSE 🦮
### Standalone AI Navigation Robot for the Visually Impaired
**Arduino Physical AI Challenge India 2026 — Robu.in × Arduino**

[![License: Unlicense](https://img.shields.io/badge/License-Unlicense-blue.svg)](https://unlicense.org)
[![Arduino UNO Q](https://img.shields.io/badge/Board-Arduino%20UNO%20Q-00979D?logo=arduino)](https://store.arduino.cc)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python)](https://python.org)
[![YOLOv5n](https://img.shields.io/badge/AI-YOLOv5n%20ONNX-EE4C2C)](https://github.com/ultralytics/yolov5)

---

> **285 million people** worldwide are visually impaired. Navigating a busy Indian city — with vehicles parked on footpaths, open manholes, stray animals, and uneven roads — is a daily challen[...]

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
╔════════════════════════════════════════════════════════════════�[...]
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
║  ┌─────────────┐  Interrupt │                                  │    ║
║  │  LM393 x2   │───────────►│  ┌──────────────────────────┐   │    ║
║  │  Encoders   │            │  │    Dead-Reckoning Odom    │   │    ║
║  └───────────���─┘            │  │    P-Controller Steering  │   │    ║
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
╚══════════════════════════════════════════════════════════╦═════[...]
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

... (remaining README content unchanged) ...

# Nemo~Sense — Proof of Concept Documentation

**Project:** Nemo~Sense  
**Version:** 1.0 POC  
**Date:** July 2026  
**Category:** Assistive Robotics / Embedded AI  

---

## 1. Problem Statement

Over 2.2 billion people worldwide have vision impairment (WHO, 2019). Existing navigation aids — white canes, guide dogs, and smartphone apps — share a common limitation: they are either passive, expensive, or require constant user attention and internet connectivity.

**Nemo~Sense** addresses this gap with a self-contained, camera-guided rover that physically leads a visually impaired user around obstacles in real time, requiring no smartphone, no internet, and no cloud compute.

---

## 2. POC Objectives

| Objective | Target | Achieved |
|---|---|---|
| Detect obstacles using only a USB webcam | ≥80% detection accuracy | ✅ YOLOv5n via cv2.dnn |
| Avoid detected obstacles autonomously | Steer within 1 second of detection | ✅ Micro-nav reactive controller |
| Drive a predefined route (north → east) | Complete both legs | ✅ Simulated GPS + waypoint nav |
| Track position without GPS | Cartesian dead reckoning | ✅ Differential-drive DR |
| Run fully standalone on battery | No PC after setup | ✅ cron auto-start |
| Total hardware cost | Under $120 | ✅ ~$119 BOM |

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Arduino UNO Q                             │
│                                                              │
│  ┌──────────────────────────────┐  ┌──────────────────────┐ │
│  │    Linux (Cortex-A53)        │  │   STM32 MCU          │ │
│  │                              │  │                      │ │
│  │  main.py (Orchestrator)      │  │  motor_controller    │ │
│  │  ├── vision.py (YOLOv5n)    │  │  .ino                │ │
│  │  ├── micro_nav.py            │  │                      │ │
│  │  ├── navigation.py           │  │  Reads MOTOR:L,R     │ │
│  │  ├── dead_reckoning.py       │◄─►│  via /dev/ttyHS1    │ │
│  │  ├── motor_link.py           │  │                      │ │
│  │  └── config.py               │  │  Drives GPIO:        │ │
│  └──────────────────────────────┘  │  D2 → Quarky Pin 1  │ │
│                                     │  D3 → Quarky Pin 2  │ │
│  Webcam → /dev/video0              │  D4 → Quarky Pin 3  │ │
│                                     └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                              │ GPIO signals
                                              ▼
                                    ┌─────────────────┐
                                    │  Quarky Chassis │
                                    │  (motors/wheels)│
                                    └─────────────────┘
```

---

## 4. Software Stack

### Python Modules (Linux side)

| Module | Purpose | Key Technology |
|---|---|---|
| `main.py` | Central orchestrator, control loop | Python threading |
| `vision.py` | Webcam capture + obstacle detection | OpenCV, YOLOv5n |
| `micro_nav.py` | Reactive obstacle avoidance | Zone-based controller |
| `navigation.py` | GPS waypoint following | Haversine formula |
| `dead_reckoning.py` | Cartesian position tracking | Differential-drive kinematics |
| `motor_link.py` | Serial command bridge to STM32 | pyserial |
| `config.py` | All system constants | — |

### Arduino Firmware (STM32 side)

`motor_controller.ino` — parses `MOTOR:left,right` serial commands from Linux and translates them into 3-pin GPIO signals (RIGHT / LEFT / STOP) that the Quarky chassis reads.

---

## 5. Control Loop (runs at ~4 Hz)

```
Every 250ms:
1. Capture frame from webcam (/dev/video0)
2. Run YOLOv5n → detect obstacles in frame
3. Map detections to LEFT / CENTRE / RIGHT zones
4. Micro-nav: compute steer command + urgency
5. Macro-nav: compute bearing to next waypoint
6. MERGE: micro-nav overrides if obstacle present
7. Compute L/R PWM values
8. Send MOTOR:left,right to STM32 via /dev/ttyHS1
9. Dead reckoning: update (x,y) Cartesian position
10. Log position + ASCII path map every 30 cycles
```

---

## 6. Obstacle Avoidance Algorithm

The `MicroNavigator` uses a three-zone reactive controller:

```
Camera frame (320px wide):
 LEFT [0–106]  |  CENTRE [106–214]  |  RIGHT [214–320]
```

| Scenario | Action |
|---|---|
| Obstacle in centre < 1.5 m | Steer to clearer side |
| Obstacle in centre < 0.5 m | Emergency STOP |
| Obstacle in left zone | Steer right |
| Obstacle in right zone | Steer left |
| No obstacles | Full speed forward |

---

## 7. Dead Reckoning

Tracks rover position on a 2D Cartesian plane from the power-on origin using differential-drive kinematics. No GPS required.

**Terminal output every 30 cycles:**
```
  +Y (north)
  │    ···●
  │   ·
  S──────────
             +X (east)
  Rover: (+0.80, +2.14) m  hdg=5.1°
```

---

## 8. Hardware

### Bill of Materials

| Component | Model | Cost |
|---|---|---|
| AI Brain + MCU | Arduino UNO Q | $45 |
| Chassis | Quarky by STEMpedia | $20 |
| Camera | Logitech C270 720p | $25 |
| Power hub | Powered USB Hub | $12 |
| Battery | 10 000 mAh power bank | $15 |
| Wires | 4× jumper wires | $2 |
| **Total** | | **~$119** |

### Wiring (Arduino → Quarky)

| Arduino Pin | Quarky Pin | Signal |
|---|---|---|
| D2 | Pin 1 | Turn Right |
| D3 | Pin 2 | Turn Left |
| D4 | Pin 3 | Emergency Stop |
| GND | GND | Shared ground |

---

## 9. Limitations & Next Steps

| Limitation | Future Fix |
|---|---|
| Simulated GPS | Add u-blox NEO-M8N ($12) via UART |
| No compass | Add MPU-6050 IMU ($1) via I²C |
| No audio alerts | Add USB speaker + pyttsx3 TTS |
| No web dashboard | Flask server → live camera + path map |

---

*Nemo~Sense POC v1.0 — Arduino UNO Q + Quarky + OpenCV*  
*License: MIT*

# GuideSense — Physical AI Challenge Submission Guide

**Competition:** [Arduino Physical AI Challenge India 2026](https://robu.in) (Robu.in)  
**Project:** Netra / GuideSense — AI guide-dog rover for visually impaired users  
**Primary hardware:** Arduino UNO Q + Quarky chassis + Android phone + BLE headphones + GPS

---

## 1. What to submit

| Item | Location in repo | Format |
|------|------------------|--------|
| Project report | `docs/competition_report.md` | PDF export |
| Architecture diagram | Inside report (Mermaid) | Include in PDF |
| Source code | Full `netra/` folder | ZIP or GitHub link |
| Demo video (2–5 min) | Record separately | MP4 / YouTube unlisted |
| Bill of materials | `README.md` + this doc | Table |
| Wiring photos | Take at build time | JPG in `docs/photos/` |

---

## 2. Elevator pitch (30 seconds)

> GuideSense is a low-cost robotic guide dog on wheels. A blind user speaks their destination into a phone app. The phone streams GPS and camera data over Bluetooth while audio guidance plays through BLE headphones. The **Arduino UNO Q** runs **YOLOv5 obstacle detection entirely on-device** — no cloud vision — and drives a **Quarky robot chassis** to steer around hazards while following GPS waypoints. It replaces a $40,000 guide dog with affordable, repairable hardware.

---

## 3. How it meets Physical AI Challenge criteria

| Criterion | How GuideSense satisfies it |
|-----------|----------------------------|
| **Arduino UNO Q as core** | Linux MPU runs Python orchestrator + ONNX YOLOv5; STM32 MCU handles real-time motor forwarding and watchdog |
| **Edge / physical AI** | YOLOv5n inference on UNO Q CPU; motor stop loop runs locally with &lt;250 ms latency |
| **Real-world problem** | Independent mobility for visually impaired users at near-zero recurring cost |
| **Sensor fusion** | Phone GPS + camera + IMU merged with on-device vision zones (left/center/right) |
| **Actuation** | Quarky differential drive with software watchdog auto-stop |

---

## 4. Demo script for judges

1. **Intro (15 s):** Show Quarky rover, UNO Q, phone on handle mount, BLE headphones on mannequin/user.
2. **Vision (30 s):** Run `python test_webcam_ai.py` — show bounding boxes on obstacles.
3. **Motors (30 s):** Run `python test_motors.py` — rover drives forward, steers, stops.
4. **Voice nav (60 s):** Open Android app → "Take me to [landmark]" → Gemini parses route → rover starts with TTS "Navigating to…".
5. **Obstacle (45 s):** Place box in path → rover slows, announces "Obstacle ahead — steering left", avoids it.
6. **Stop (15 s):** User says "Stop" → motors halt, TTS confirms.

---

## 5. Bill of materials (competition table)

| # | Component | Qty | Role | Approx. cost (INR) |
|---|-----------|-----|------|-------------------|
| 1 | Arduino UNO Q | 1 | Edge AI brain + MCU bridge | — |
| 2 | Quarky robot (STEMpedia) | 1 | Motor chassis + wheels | — |
| 3 | Android smartphone | 1 | Voice, GPS, camera, Gemini API | — |
| 4 | BLE headphones | 1 | Hands-free audio I/O | — |
| 5 | USB webcam (optional) | 1 | Fallback vision if no phone camera | — |
| 6 | 18650 battery pack | 1 | Quarky / rover power | — |
| 7 | 5 V buck converter | 1 | UNO Q power from battery | — |
| 8 | Jumper wires | 1 set | UNO Q ↔ Quarky UART | — |

*Total recurring cost for user: phone they already own + ~₹15,000–25,000 rover hardware vs. ₹30L+ for a guide dog.*

---

## 6. Team / attribution block (fill in)

```
Team Name:     ___________________________
Members:       ___________________________
School/Org:    ___________________________
Mentor:        ___________________________
City:          ___________________________
GitHub/Repo:   ___________________________
Video URL:     ___________________________
```

---

## 7. Pre-submission checklist

- [ ] `motor_controller.ino` uploaded to UNO Q MCU (`USE_QUARKY_BRIDGE = 1`)
- [ ] `guidesense_quarky_receiver.py` uploaded to Quarky via PictoBlox
- [ ] `scripts/setup_q.sh` completed on UNO Q
- [ ] YOLO model at `python/models/yolov5n.onnx`
- [ ] `python main.py --mode indoor` runs without import errors
- [ ] Android app pairs with UNO Q Bluetooth (`NetraGuide`)
- [ ] BLE headphones connected to phone for TTS output
- [ ] Demo video recorded with obstacle avoidance visible
- [ ] Report exported to PDF from `docs/competition_report.md`

---

## 8. Quick deploy (day of demo)

```bash
# On your PC (Windows)
deploy.bat
# Enter UNO Q IP → pushes python/ and starts main.py

# On UNO Q directly
source /root/netra/venv/bin/activate
cd /root/netra/python
python main.py --mode full
```

For indoor venue without GPS:

```bash
python main.py --mode indoor
```

---

## 9. Contact & support links

- STEMpedia Quarky docs: https://ai.thestempedia.com/docs/quarky/
- Arduino UNO Q: https://docs.arduino.cc/
- Robu.in Physical AI Challenge: check robu.in for 2026 registration page

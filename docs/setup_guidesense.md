# GuideSense — Complete Setup Guide

Step-by-step instructions to get the rover running for the Physical AI Challenge.

---

## Phase A — Hardware assembly

### A1. Power

1. Connect 2×18650 in series (7.4 V) to Quarky power input.
2. Use a 5 V buck converter from the same pack to power the UNO Q `5V` pin.
3. Tie all grounds together: battery (−), Quarky GND, UNO Q GND.

### A2. Quarky ↔ UNO Q UART

| UNO Q | Quarky |
|-------|--------|
| D0 (TX) | RX |
| GND | GND |

Use 10 cm jumper wires. Keep UART wires away from motor power cables to reduce noise.

### A3. Phone mount

Mount the Android phone on the Quarky handle facing forward. Connect a USB power bank to the phone if needed.

### A4. BLE headphones

Pair Bluetooth headphones with the phone. All TTS navigation prompts route to them automatically when connected.

### A5. Optional USB webcam

Plug into UNO Q USB host as fallback if phone camera stream is unavailable.

---

## Phase B — Firmware upload

### B1. UNO Q MCU (5 minutes)

1. Connect UNO Q to PC via USB.
2. Arduino IDE 2 → Board: **Arduino UNO Q** → Target: **MCU**.
3. Open `arduino/motor_controller/motor_controller.ino`.
4. Verify `#define USE_QUARKY_BRIDGE 1`.
5. Upload.

### B2. Quarky receiver (10 minutes)

1. Connect Quarky to PC via USB-C.
2. Open PictoBlox → Board: Quarky → Connect.
3. Python Coding → Upload Mode.
4. Paste `quarky/guidesense_quarky_receiver.py`.
5. Upload → wait for success message.
6. Disconnect from PC → wire to UNO Q (Phase A2).

---

## Phase C — UNO Q Linux setup (20 minutes)

### C1. Network

Connect UNO Q to Wi-Fi. Note its IP address (serial console or router DHCP list).

### C2. Deploy from Windows

```bat
cd C:\Users\Admin\.gemini\antigravity\scratch\netra
deploy.bat
```

Enter IP → answer `y` for first-time setup.

### C3. Manual setup (alternative)

```bash
ssh root@<IP>
apt update && apt install -y python3-venv python3-opencv bluetooth bluez
cd /root/netra
bash scripts/setup_q.sh
bash scripts/download_models.sh
```

---

## Phase D — Verification tests

Run in order. Do not skip steps.

### D1. YOLO vision (PC or UNO Q)

```bash
python test_webcam_ai.py
```

Expected: bounding boxes on people/objects in webcam feed.

### D2. Quarky motors alone

```bash
python test_quarky.py COM5        # Windows, Quarky on USB
python test_quarky.py /dev/ttyUSB0  # Linux
```

Expected: forward → stop → steer left → steer right.

### D3. MCU bridge (UNO Q wired to Quarky)

```bash
python test_motors.py /dev/ttyACM0
```

Expected: `READY`, `ACK`, `HEARTBEAT`, Quarky wheels move.

### D4. Full brain (indoor)

```bash
bash scripts/run_netra.sh indoor
```

Place an object in front of the camera. Expected log: obstacle detection + motor steer commands.

---

## Phase E — Android app

1. Open `GuideSenseApp/` in Android Studio.
2. Build → install on phone.
3. Grant: Microphone, Location, Bluetooth, Camera.
4. Pair phone Bluetooth with UNO Q (`NetraGuide`).
5. Open app → tap microphone → say "Start" or speak a destination.

---

## Phase F — Competition demo day

| Time | Action |
|------|--------|
| T−30 min | Charge batteries, test `test_motors.py` |
| T−15 min | Start `bash scripts/run_netra.sh indoor` |
| T−5 min | Open Android app, confirm BT connected |
| Demo | Voice command → walk with rover → show obstacle avoid |

Bring printed copy of `docs/competition_report.md` and wiring photo.

---

## Quick reference — run modes

```bash
python main.py --mode indoor      # Best for demo venue (no GPS needed)
python main.py --mode full        # Outdoor with phone GPS
python main.py --mode demo        # Keyboard: w=start, s=stop
python main.py --mode vision-only # Camera test only
python main.py --mode motor-test  # Manual PWM: type "150,150"
```

---

## Getting help

- Motor issues → `docs/quarky_bridge.md`
- Submission → `docs/submission_guide.md`
- Wiring → `docs/hardware_wiring.md` (L298N legacy) or Quarky bridge doc

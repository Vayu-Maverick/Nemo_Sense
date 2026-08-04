# GuideSense (Netra) — Quarky ↔ Arduino UNO Q Bridge

This guide explains how the **Quarky robot chassis** connects to the **Arduino UNO Q** for the Robu.in Physical AI Challenge.

## Architecture

```
┌─────────────────┐   Bluetooth SPP    ┌──────────────────────────────────────┐
│  Android Phone  │◄──────────────────►│  Arduino UNO Q — Linux (MPU)         │
│  Voice / GPS /  │   camera + sensors │  main.py — YOLOv5 + navigation       │
│  BLE headphones │                    └──────────────┬───────────────────────┘
└─────────────────┘                                   │ RouterBridge serial
                                                      ▼
                                    ┌──────────────────────────────────────┐
                                    │  Arduino UNO Q — STM32 (MCU)         │
                                    │  motor_controller.ino                │
                                    │  Forwards MOTOR:left,right           │
                                    └──────────────┬───────────────────────┘
                                                   │ UART 115200 (D0 TX → Quarky RX)
                                                   ▼
                                    ┌──────────────────────────────────────┐
                                    │  Quarky Robot Chassis                │
                                    │  guidesense_quarky_receiver.py       │
                                    │  Drives L/R motors                   │
                                    └──────────────────────────────────────┘
```

The UNO Q runs **edge AI** (YOLOv5 ONNX on Linux). Quarky is **actuation only** — it receives motor commands and moves. This satisfies the Physical AI Challenge requirement that the UNO Q performs the AI inference locally.

## Wiring (recommended: UART bridge)

| UNO Q pin | Quarky pin | Notes |
|-----------|------------|-------|
| D0 (TX)   | RX / Serial IN | Motor commands from MCU |
| GND       | GND        | **Required — common ground** |
| 5 V (optional) | 5 V   | Only if Quarky is not on its own battery |

**Do not** connect UNO Q TX to Quarky TX. Cross TX→RX only.

### Alternative: USB direct (no MCU UART)

Plug Quarky into the UNO Q USB host port. Set on the UNO Q:

```bash
export NETRA_MOTOR_BACKEND=quarky_usb
export NETRA_QUARKY_PORT=/dev/ttyUSB0   # or /dev/ttyACM1 — check dmesg
```

Upload `quarky/guidesense_quarky_receiver.py` to Quarky via PictoBlox. Linux sends `MOTOR:` commands directly over USB serial.

## Flash order

### Step 1 — STM32 MCU (UNO Q)

1. Open Arduino IDE 2.x → board **Arduino UNO Q**.
2. Open `arduino/motor_controller/motor_controller.ino`.
3. Confirm `#define USE_QUARKY_BRIDGE 1` at the top.
4. Upload to the **MCU** target (not the Linux side).

### Step 2 — Quarky receiver

1. Open **PictoBlox** → Board: **Quarky** → connect USB.
2. Python Coding → **Upload Mode**.
3. Paste contents of `quarky/guidesense_quarky_receiver.py`.
4. Click **Upload**.
5. Disconnect Quarky from PC; wire to UNO Q as above.

### Step 3 — UNO Q Linux brain

```bash
ssh root@<UNO_Q_IP>
cd /root/netra && bash scripts/setup_q.sh
source venv/bin/activate
cd python && python main.py --mode indoor
```

## Wire protocol

All links use the same ASCII protocol at **115200 baud**, newline-terminated:

| Command | Example | Action |
|---------|---------|--------|
| Forward differential | `MOTOR:150,150` | Both wheels forward |
| Steer left | `MOTOR:40,150` | Slow left, fast right |
| Stop | `MOTOR:0,0` | Emergency / idle stop |
| Ping | `PING` | Handshake (`PONG` / `ACK:PONG`) |

PWM range: **-255 … +255** (negative = reverse).

## Testing

### 1. Test Quarky alone (PC)

Connect Quarky via USB to your PC. In PictoBlox serial monitor or:

```bash
python test_quarky.py COM5
```

### 2. Test MCU bridge (PC → UNO Q USB)

With UNO Q connected to PC:

```bash
python test_motors.py COM4
```

You should see `READY`, `ACK`, and `HEARTBEAT`. Quarky wheels should move if wired.

### 3. Test full stack on UNO Q

```bash
python main.py --mode demo
```

Type `w` to start, `s` to stop. Obstacle avoidance uses the USB webcam or phone camera stream.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| YOLO works, no movement | Flash `motor_controller.ino`, not `q_mcu_motor.ino` |
| MCU READY but Quarky still | Check TX→RX wiring and common GND |
| Quarky jitters / wrong direction | Re-upload receiver; calibrate motors in PictoBlox settings |
| `/dev/ttyACM0` missing | `ls /dev/ttyACM*` after plugging UNO Q |
| Bluetooth won't connect | Run `bluetoothctl discoverable on` on UNO Q |

## Legacy L298N mode

If you revert to a raw L298N driver board, set in `motor_controller.ino`:

```cpp
#define USE_QUARKY_BRIDGE  0
```

Wire per `docs/hardware_wiring.md` and set `MOTOR_BACKEND=l298n`.

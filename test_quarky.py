#!/usr/bin/env python3
"""
test_quarky.py — Send MOTOR commands directly to Quarky over USB serial.

Use this to verify the Quarky receiver script before connecting to the UNO Q.

Usage:
    python test_quarky.py              # auto-detect COM port (Windows)
    python test_quarky.py COM5
    python test_quarky.py /dev/ttyUSB0
    python test_quarky.py --dry
"""

import sys
import time

DRY = "--dry" in sys.argv
PORT = None
for arg in sys.argv[1:]:
    if not arg.startswith("-"):
        PORT = arg

BAUD = 115200

STEPS = [
    ("MOTOR:100,100", 2.0, "Forward slow"),
    ("MOTOR:0,0", 1.0, "Stop"),
    ("MOTOR:40,150", 1.5, "Steer left"),
    ("MOTOR:0,0", 1.0, "Stop"),
    ("MOTOR:150,40", 1.5, "Steer right"),
    ("MOTOR:0,0", 1.0, "Stop"),
    ("MOTOR:200,200", 2.0, "Forward fast"),
    ("MOTOR:0,0", 0.5, "Final stop"),
]


def find_port():
    if PORT:
        return PORT
    try:
        from serial.tools.list_ports import comports
        for p in comports():
            desc = (p.description or "").lower()
            if "quarky" in desc or "usb" in desc or "serial" in desc or "ch340" in desc:
                return p.device
        ports = list(comports())
        if ports:
            return ports[0].device
    except ImportError:
        pass
    return "COM5"


def main():
    port = find_port()
    print(f"GuideSense Quarky motor test — port={port} dry={DRY}")

    ser = None
    if not DRY:
        import serial
        ser = serial.Serial(port, BAUD, timeout=0.5)
        time.sleep(2.0)
        ser.reset_input_buffer()

    for cmd, duration, label in STEPS:
        print(f"  >> {cmd}  ({label}, {duration}s)")
        if ser:
            ser.write((cmd + "\n").encode("ascii"))
            ser.flush()
            deadline = time.time() + duration
            while time.time() < deadline:
                if ser.in_waiting:
                    line = ser.readline().decode("ascii", errors="replace").strip()
                    if line:
                        print(f"  << {line}")
                time.sleep(0.05)
        else:
            time.sleep(duration)

    if ser:
        ser.close()
    print("Done.")


if __name__ == "__main__":
    main()

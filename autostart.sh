#!/bin/bash
# autostart.sh — Netra Blind Guide Rover boot script
# Runs as the arduino user at system startup

# 1. Force USB host mode so OTG webcam gets power
#    GPIO 70 on gpiochip1 = USB VBUS enable on Arduino UNO Q
#    Must run BEFORE the main python script
echo "[autostart] Enabling USB VBUS (GPIO 70) for OTG webcam..."
gpioset -c /dev/gpiochip1 -t0 70=1 2>/dev/null && \
    echo "[autostart] USB VBUS enabled" || \
    echo "[autostart] VBUS enable failed (may need arduino-router ready signal)"

sleep 2

# 2. Disable USB autosuspend for all connected devices
if [ -d /sys/bus/usb/devices ]; then
    for dev in /sys/bus/usb/devices/*/power/control; do
        [ -f "$dev" ] && echo on > "$dev" 2>/dev/null || true
    done
fi

# 3. Wait for OTG webcam to enumerate (up to 10s)
echo "[autostart] Waiting for webcam..."
for i in $(seq 1 10); do
    for vid in /dev/video*; do
        if [ -e "$vid" ]; then
            if v4l2-ctl -d "$vid" --info 2>/dev/null | grep -q "Bus info.*usb"; then
                echo "[autostart] Webcam found at $vid"
                break 2
            fi
        fi
    done
    sleep 1
done

# 4. Wait for arduino-router to be ready (STM32 bridge)
echo "[autostart] Waiting for arduino-router..."
for i in $(seq 1 20); do
    if [ -S /var/run/arduino-router.sock ]; then
        echo "[autostart] arduino-router socket ready"
        break
    fi
    sleep 1
done

# 5. Install pynmea2 if missing (needed for GPS)
python3 -c "import pynmea2" 2>/dev/null || pip3 install pynmea2 --quiet

# 6. Go to project directory
cd /home/arduino/nemosense/python

# 7. Start main script with restart loop
while true; do
    echo "[autostart] Starting Netra..."
    /usr/bin/python3 -u main.py --mode full
    echo "[autostart] Netra exited, restarting in 5s..."
    sleep 5
done

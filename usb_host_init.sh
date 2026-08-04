#!/bin/bash
# usb_host_init.sh — Switch USB-C to host mode and power webcam
#
# This script runs at boot (as root via systemd) to:
# 1. Tear down the ADB USB gadget (releases the USB-C port from device mode)
# 2. Switch the port to host/source mode (so it can power the hub + webcam)
# 3. Enable VBUS power
# 4. Wait for the webcam UVC device to enumerate
#
# After this script runs, /dev/video2 (or similar) will appear.

set -e

log() { echo "[usb-host-init] $*" | tee /dev/kmsg 2>/dev/null || true; }

log "Starting USB host mode init..."

# Step 1: Tear down ADB gadget so USB-C port is freed
if [ -f /sys/kernel/config/usb_gadget/g1/UDC ]; then
    log "Disabling ADB USB gadget..."
    echo "" > /sys/kernel/config/usb_gadget/g1/UDC 2>/dev/null || true
fi

sleep 1

# Step 2: Switch USB-C data role to host
TYPEC_PORT="/sys/class/typec/port0"
if [ -f "$TYPEC_PORT/data_role" ]; then
    log "Switching USB-C to host mode..."
    echo host > "$TYPEC_PORT/data_role" 2>/dev/null || log "data_role switch failed (may need CC negotiation)"
fi

# Step 3: Switch power role to source (so it can power devices)
if [ -f "$TYPEC_PORT/power_role" ]; then
    log "Switching USB-C power role to source..."
    echo source > "$TYPEC_PORT/power_role" 2>/dev/null || log "power_role switch failed"
fi

sleep 1

# Step 4: Enable VBUS regulator (powers the USB hub)
VBUS_REG="/sys/devices/platform/soc@0/1c40000.spmi/spmi-0/0-00/1c40000.spmi:pmic@0:usb-vbus-regulator@1100/regulator/regulator.20"
if [ -d "$VBUS_REG" ]; then
    log "Enabling VBUS regulator..."
    echo enabled > "$VBUS_REG/state" 2>/dev/null || log "VBUS enable failed (may auto-enable)"
fi

# Step 5: Disable USB autosuspend for all devices
log "Disabling USB autosuspend..."
for dev in /sys/bus/usb/devices/*/power/control; do
    [ -f "$dev" ] && echo on > "$dev" 2>/dev/null || true
done

# Step 6: Wait for UVC webcam to enumerate (up to 15 seconds)
log "Waiting for webcam..."
for i in $(seq 1 15); do
    if ls /dev/video* 2>/dev/null | grep -q video; then
        # Check if any video device is a real camera (not codec)
        for vid in /dev/video*; do
            if v4l2-ctl -d "$vid" --info 2>/dev/null | grep -q "Bus info.*usb"; then
                log "Webcam found at $vid"
                # Wake it up with a dummy query
                v4l2-ctl -d "$vid" --list-formats-ext > /dev/null 2>&1 || true
                exit 0
            fi
        done
    fi
    sleep 1
done

log "Webcam not found after 15s — continuing anyway"
exit 0

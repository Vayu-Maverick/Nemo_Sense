# quarky_wifi_receiver.py
# ========================
# MicroPython script for Quarky (ESP32) to receive motor commands over WiFi (UDP).
# 
# Upload this to your Quarky board using Thonny or PictoBlox Python.
# It connects to your mobile hotspot/WiFi and listens for "M:LEFT,RIGHT\n" UDP packets.

import network
import socket
import time

try:
    from quarky import *
    qrk = Quarky()
except ImportError:
    print("Warning: quarky module not found. Are you running on the Quarky board?")
    qrk = None

SSID = "YOUR_HOTSPOT_NAME"
PWD  = "YOUR_HOTSPOT_PASSWORD"
PORT = 8080

# -- WiFi Connection --
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PWD)

print("Connecting to WiFi:", SSID)
while not wlan.isconnected():
    time.sleep(0.5)
    print(".", end="")
    
ip = wlan.ifconfig()[0]
print("\nConnected! My IP is:", ip)

# -- UDP Socket --
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', PORT))
sock.settimeout(0.5)

print("Listening for UDP commands on port", PORT)
print("-> In run_nemo_demo.bat, use option 2 or 3 and enter this IP:", ip)

last_cmd = time.ticks_ms()

while True:
    try:
        data, addr = sock.recvfrom(64)
        msg = data.decode().strip()
        
        if msg.startswith("M:"):
            parts = msg[2:].split(',')
            if len(parts) == 2:
                l = max(-255, min(255, int(parts[0])))
                r = max(-255, min(255, int(parts[1])))
                
                # Map -255..255 from laptop to 0..100 % for Quarky
                l_pct = int(max(0, min(100, abs(l) / 2.55)))
                r_pct = int(max(0, min(100, abs(r) / 2.55)))
                
                if qrk:
                    if l > 0: qrk.runmotor("L", "FORWARD", l_pct)
                    elif l < 0: qrk.runmotor("L", "BACKWARD", l_pct)
                    else: qrk.runmotor("L", "FORWARD", 0)
                    
                    if r > 0: qrk.runmotor("R", "FORWARD", r_pct)
                    elif r < 0: qrk.runmotor("R", "BACKWARD", r_pct)
                    else: qrk.runmotor("R", "FORWARD", 0)
                    
                last_cmd = time.ticks_ms()
    except OSError:
        # Timeout (no data received in 0.5s)
        pass
        
    # Watchdog: Stop motors if no command received for 500ms
    if time.ticks_diff(time.ticks_ms(), last_cmd) > 500:
        if qrk:
            qrk.runmotor("L", "FORWARD", 0)
            qrk.runmotor("R", "FORWARD", 0)

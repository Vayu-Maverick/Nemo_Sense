# pictoblox_bridge.py
# ========================================================
# Run this script INSIDE PictoBlox (Python Coding mode).
# It creates a local bridge so the Nemo Sense AI (running 
# in standard Python) can control your Quarky while it is 
# connected to PictoBlox via BLE!
# ========================================================

import socket
import time

try:
    from quarky import *
    qrk = Quarky()
    print("Quarky object initialized!")
except ImportError:
    print("Please run this script inside PictoBlox.")
    qrk = None

# Listen for Nemo Sense commands locally
UDP_IP = "127.0.0.1"
UDP_PORT = 8080

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.settimeout(0.1)  # Non-blocking

print("========================================")
print(" PictoBlox UDP Bridge is READY!")
print("========================================")
print("Listening on 127.0.0.1 : 8080")
print("If you see 'RECEIVED' messages below, the connection is working!")
print("========================================\n")

last_cmd = time.time()
last_print = 0

while True:
    try:
        data, addr = sock.recvfrom(1024)
        msg = data.decode('utf-8').strip()
        
        if msg.startswith("M:"):
            parts = msg[2:].split(',')
            if len(parts) == 2:
                l = int(parts[0])
                r = int(parts[1])
                
                # Convert -255..255 from AI into 0..100% for PictoBlox
                l_pct = int(max(0, min(100, abs(l) / 2.55)))
                r_pct = int(max(0, min(100, abs(r) / 2.55)))
                
                # Only print every 0.5s to avoid flooding the PictoBlox console
                if time.time() - last_print > 0.5:
                    print(f"RECEIVED -> AI Left: {l} | AI Right: {r}  =>  Quarky: {l_pct}%, {r_pct}%")
                    last_print = time.time()
                
                if qrk:
                    # LEFT MOTOR
                    if l > 0:
                        qrk.runmotor("L", "FORWARD", l_pct)
                    elif l < 0:
                        qrk.runmotor("L", "BACKWARD", l_pct)
                    else:
                        qrk.runmotor("L", "FORWARD", 0)
                        
                    # RIGHT MOTOR
                    if r > 0:
                        qrk.runmotor("R", "FORWARD", r_pct)
                    elif r < 0:
                        qrk.runmotor("R", "BACKWARD", r_pct)
                    else:
                        qrk.runmotor("R", "FORWARD", 0)
                    
                last_cmd = time.time()
                
    except socket.timeout:
        pass
    except Exception as e:
        print("Error:", e)
        
    # Safety Watchdog: stop motors if AI crashes or stops sending for 1 second
    if time.time() - last_cmd > 1.0:
        if qrk:
            qrk.runmotor("L", "FORWARD", 0)
            qrk.runmotor("R", "FORWARD", 0)

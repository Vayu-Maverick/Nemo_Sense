# quarky_ble_receiver.py
# ========================
# MicroPython script for Quarky (ESP32) to receive motor commands over BLE.
# 
# Upload this to your Quarky board using Thonny or ampy.
# It advertises a BLE service and listens for "M:LEFT,RIGHT\n" strings.

import machine
import bluetooth
import time

# -- BLE UUIDs --
SERVICE_UUID = bluetooth.UUID("19B10000-E8F2-537E-4F6C-D104768A1214")
CHAR_UUID    = bluetooth.UUID("19B10001-E8F2-537E-4F6C-D104768A1214")

# -- State --
TIMEOUT_MS = 500
last_cmd_ticks = time.ticks_ms()

# Initialize Quarky board
try:
    from quarky import *
    qrk = Quarky()
except ImportError:
    print("Warning: quarky module not found. Are you running on the Quarky board?")
    qrk = None

def set_motors(l, r):
    if not qrk:
        return
        
    # Map -255..255 from laptop to 0..100 % for Quarky inbuilt drivers
    l_pct = int(max(0, min(100, abs(l) / 2.55)))
    r_pct = int(max(0, min(100, abs(r) / 2.55)))
    
    # Left Motor
    if l > 0:
        qrk.runmotor("L", "FORWARD", l_pct)
    elif l < 0:
        qrk.runmotor("L", "BACKWARD", l_pct)
    else:
        qrk.runmotor("L", "FORWARD", 0)
        
    # Right Motor
    if r > 0:
        qrk.runmotor("R", "FORWARD", r_pct)
    elif r < 0:
        qrk.runmotor("R", "BACKWARD", r_pct)
    else:
        qrk.runmotor("R", "FORWARD", 0)

# -- BLE Setup --
class BLEServer:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self.ble_irq)
        
        ((self.char_handle,),) = self.ble.gatts_register_services((
            (SERVICE_UUID, ((CHAR_UUID, bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE),)),
        ))
        
        self.connections = set()
        self.advertise()

    def advertise(self):
        name = "Quarky_Nemo"
        payload = bytearray([len(name) + 1, 0x09]) + name.encode()
        self.ble.gap_advertise(100, payload)
        print("BLE Advertising as", name)

    def ble_irq(self, event, data):
        global last_cmd_ticks
        if event == 1: # _IRQ_CENTRAL_CONNECT
            conn_handle, _, _ = data
            self.connections.add(conn_handle)
            print("Connected")
        elif event == 2: # _IRQ_CENTRAL_DISCONNECT
            conn_handle, _, _ = data
            self.connections.remove(conn_handle)
            print("Disconnected")
            set_motors(0, 0)
            self.advertise()
        elif event == 3: # _IRQ_GATTS_WRITE
            conn_handle, attr_handle = data
            if attr_handle == self.char_handle:
                msg = self.ble.gatts_read(self.char_handle).decode().strip()
                if msg.startswith("M:"):
                    try:
                        parts = msg[2:].split(',')
                        if len(parts) == 2:
                            l = max(-255, min(255, int(parts[0])))
                            r = max(-255, min(255, int(parts[1])))
                            set_motors(l, r)
                            last_cmd_ticks = time.ticks_ms()
                    except ValueError:
                        pass

server = BLEServer()
print("MicroPython BLE Receiver running...")
set_motors(0, 0)

while True:
    if time.ticks_diff(time.ticks_ms(), last_cmd_ticks) > TIMEOUT_MS:
        set_motors(0, 0)
    time.sleep_ms(50)
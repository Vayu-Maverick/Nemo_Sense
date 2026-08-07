from __future__ import annotations
import cv2
import serial
import json
import time
import threading
import socket
import subprocess
import numpy as np
from pathlib import Path
import math
import sys
import logging

logger = logging.getLogger("netra.q_brain")

# --- Configuration ---
BLUETOOTH_PORT = 1 
SERIAL_PORT = '/dev/ttyACM0'  
SERIAL_BAUD = 115200
CAMERA_INDEX = 0
YOLO_MODEL = 'yolov5n.onnx'  
CONFIDENCE_THRESHOLD = 0.45
DANGER_DISTANCE = 0.5  

# Dead Reckoning Config
WHEEL_CIRCUMFERENCE_CM = 20.4  # Approx 65mm wheel diameter
TICKS_PER_REV = 20  # Typical LM393 encoder disk

class MotorController:
    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
        self.ser = None
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.last_left_ticks = 0
        self.last_right_ticks = 0
        self.wheel_base_cm = 15.0 # Distance between wheels
        
    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
            print("Connected to MCU")
            # Reset ticks
            self.ser.write(b"R:TICKS\n")
            threading.Thread(target=self._read_telemetry, daemon=True).start()
        except Exception as e:
            print(f"Failed to connect to MCU: {e}")
            
    def _read_telemetry(self):
        while True:
            if self.ser and self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8').strip()
                if line.startswith("E:"):
                    try:
                        parts = line[2:].split(',')
                        lticks = int(parts[0])
                        rticks = int(parts[1])
                        self._update_odometry(lticks, rticks)
                    except ValueError:
                        pass
            time.sleep(0.01)

    def _update_odometry(self, lticks, rticks):
        # Calculate delta distance for each wheel
        dl = (lticks - self.last_left_ticks) * (WHEEL_CIRCUMFERENCE_CM / TICKS_PER_REV)
        dr = (rticks - self.last_right_ticks) * (WHEEL_CIRCUMFERENCE_CM / TICKS_PER_REV)
        
        self.last_left_ticks = lticks
        self.last_right_ticks = rticks
        
        dc = (dl + dr) / 2.0  # Center distance
        dtheta = (dr - dl) / self.wheel_base_cm
        
        self.x += dc * math.cos(self.theta + dtheta/2.0)
        self.y += dc * math.sin(self.theta + dtheta/2.0)
        self.theta += dtheta

    def send_command(self, left, right):
        if self.ser and self.ser.is_open:
            cmd = f"MOTOR:{int(left)},{int(right)}\n"
            self.ser.write(cmd.encode('utf-8'))
            
    def stop(self):
        self.send_command(0, 0)
        
    def get_position(self):
        return {"x_cm": round(self.x, 2), "y_cm": round(self.y, 2), "heading_rad": round(self.theta, 3)}

class BluetoothServer:
    def __init__(self):
        self.server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self.client_sock = None
        self.latest_command = None
        self.running = False
        
    def start(self):
        try:
            self.server_sock.bind((socket.BDADDR_ANY, BLUETOOTH_PORT))
            self.server_sock.listen(1)
            self.running = True
            threading.Thread(target=self._accept_loop, daemon=True).start()
            print("Bluetooth server listening...")
        except Exception as e:
            print(f"WARNING: Could not start Bluetooth server ({e}). Continuing without BLE.")
            self.running = False
        
    def _accept_loop(self):
        while self.running:
            try:
                print("Waiting for BT connection...")
                client, info = self.server_sock.accept()
                print(f"Connected to {info}")
                self.client_sock = client
                self._receive_loop()
            except Exception as e:
                print(f"BT Error: {e}")
                self.client_sock = None
                
    def _receive_loop(self):
        buffer = ""
        while self.running and self.client_sock:
            try:
                data = self.client_sock.recv(1024).decode('utf-8')
                if not data: break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    self._handle_message(line)
            except:
                break
        print("BT Disconnected")
        self.client_sock = None
        
    def _handle_message(self, line):
        try:
            msg = json.loads(line)
            if msg.get('type') == 'command':
                self.latest_command = msg
        except Exception: pass
            
    def send_message(self, msg_dict):
        if self.client_sock:
            try:
                data = json.dumps(msg_dict) + '\n'
                self.client_sock.send(data.encode('utf-8'))
            except:
                self.client_sock = None

class VisionSystem:
    def __init__(self, model_path):
        self.net = cv2.dnn.readNetFromONNX(model_path)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        
    def detect(self, frame):
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
        self.net.setInput(blob)
        preds = self.net.forward()
        
        obstacles = []
        preds = np.squeeze(preds[0])
        for row in preds:
            conf = row[4]
            if conf > CONFIDENCE_THRESHOLD:
                # We want to avoid ALL obstacles (people, walls, chairs, etc.)
                w, h = row[2], row[3]
                x = row[0]
                box_area = w * h
                frame_area = 640 * 640
                relative_size = box_area / frame_area
                
                zone = "center"
                if x < 213: zone = "left"
                elif x > 426: zone = "right"
                
                obstacles.append({
                    "zone": zone,
                    "proximity": float(relative_size)
                })
        return obstacles

# ===========================================================================
# WiFi Sensing System (standalone — no dependency on wifi_sensing.py)
# ===========================================================================

class WiFiSensingSystem:
    """Background WiFi scanner that detects obstacles via RSSI shadow-fading."""

    SCAN_INTERVAL = 0.5          # seconds between scans
    SHADOW_FADE_DB = 6.0         # dB drop from baseline → obstacle
    BASELINE_ALPHA = 0.1         # EMA weight for baseline update
    PATH_LOSS_EXP = 2.7          # indoor path-loss exponent
    REF_RSSI = -40.0             # RSSI at 1 m

    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        # BSSID → {"rssi": float, "baseline": float, "ssid": str}
        self._networks: dict[str, dict] = {}
        self._zone_confidence = {"left": 0.0, "center": 0.0, "right": 0.0}
        self._obstacle_detected = False

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._scan_loop, daemon=True, name="wifi-scan"
        )
        self._thread.start()
        logger.info("WiFi sensing background scanner started")

    def stop(self):
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────

    def get_zone_confidence(self) -> dict:
        """Return zone-based obstacle confidence {left, center, right} in [0,1]."""
        with self._lock:
            return dict(self._zone_confidence)

    def is_obstacle_detected(self) -> bool:
        with self._lock:
            return self._obstacle_detected

    def get_network_count(self) -> int:
        with self._lock:
            return len(self._networks)

    def get_signal_quality(self) -> float:
        """Average signal quality across all tracked networks [0,1]."""
        with self._lock:
            if not self._networks:
                return 0.0
            rssi_vals = [n["rssi"] for n in self._networks.values()]
            avg = sum(rssi_vals) / len(rssi_vals)
            # Map -100..-30 dBm to 0..1
            return max(0.0, min(1.0, (avg + 100) / 70.0))

    # ── Background scanner ────────────────────────────────────────────────

    def _scan_loop(self):
        while self._running:
            try:
                results = self._do_scan()
                self._process_results(results)
            except Exception as exc:
                logger.debug("WiFi scan cycle error: %s", exc)
            time.sleep(self.SCAN_INTERVAL)

    def _do_scan(self) -> list[dict]:
        """Run a WiFi scan using OS tools. Returns list of {bssid, ssid, rssi, freq}."""
        results = []
        if sys.platform.startswith("linux"):
            try:
                out = subprocess.check_output(
                    ["iw", "dev", "wlan0", "scan", "-u"],
                    stderr=subprocess.DEVNULL, timeout=5,
                ).decode("utf-8", errors="replace")
                current: dict = {}
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("BSS "):
                        if current.get("bssid"):
                            results.append(current)
                        bssid = line.split()[1].split("(")[0]
                        current = {"bssid": bssid, "ssid": "", "rssi": -100, "freq": 2412}
                    elif line.startswith("signal:"):
                        try:
                            current["rssi"] = float(line.split()[1])
                        except (ValueError, IndexError):
                            pass
                    elif line.startswith("freq:"):
                        try:
                            current["freq"] = int(line.split()[1])
                        except (ValueError, IndexError):
                            pass
                    elif line.startswith("SSID:"):
                        current["ssid"] = line.split(":", 1)[1].strip()
                if current.get("bssid"):
                    results.append(current)
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                pass
        elif sys.platform == "win32":
            try:
                out = subprocess.check_output(
                    ["netsh", "wlan", "show", "networks", "mode=Bssid"],
                    stderr=subprocess.DEVNULL, timeout=5,
                ).decode("utf-8", errors="replace")
                current = {}
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("SSID") and ":" in line and "BSSID" not in line:
                        if current.get("bssid"):
                            results.append(current)
                        current = {"ssid": line.split(":", 1)[1].strip(), "bssid": "", "rssi": -100, "freq": 2412}
                    elif line.startswith("BSSID") and ":" in line:
                        current["bssid"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Signal") and ":" in line:
                        try:
                            pct = int(line.split(":")[1].strip().replace("%", ""))
                            current["rssi"] = pct / 2.0 - 100  # rough conversion
                        except ValueError:
                            pass
                    elif line.startswith("Channel") and ":" in line:
                        try:
                            ch = int(line.split(":")[1].strip())
                            current["freq"] = 2407 + ch * 5 if ch <= 14 else 5000 + ch * 5
                        except ValueError:
                            pass
                if current.get("bssid"):
                    results.append(current)
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                pass
        return results

    def _process_results(self, results: list[dict]):
        """Update baselines and detect shadow-fading obstacles."""
        with self._lock:
            obstacle_count = 0
            for r in results:
                bssid = r.get("bssid", "")
                rssi = r.get("rssi", -100)
                if not bssid:
                    continue
                if bssid in self._networks:
                    entry = self._networks[bssid]
                    entry["rssi"] = rssi
                    # EMA baseline
                    entry["baseline"] = (
                        self.BASELINE_ALPHA * rssi
                        + (1 - self.BASELINE_ALPHA) * entry["baseline"]
                    )
                    # Shadow-fading detection
                    drop = entry["baseline"] - rssi
                    if drop > self.SHADOW_FADE_DB:
                        obstacle_count += 1
                else:
                    self._networks[bssid] = {
                        "rssi": rssi,
                        "baseline": rssi,
                        "ssid": r.get("ssid", ""),
                    }

            self._obstacle_detected = obstacle_count > 0
            # Distribute obstacle confidence across zones (simple heuristic)
            conf = min(1.0, obstacle_count / max(1, len(self._networks)) * 3.0)
            # Without directional WiFi we spread equally
            self._zone_confidence = {
                "left": conf * 0.3,
                "center": conf * 0.6,
                "right": conf * 0.3,
            }

    def rssi_to_distance(self, rssi: float) -> float:
        """Convert RSSI to estimated distance in metres."""
        if rssi >= self.REF_RSSI:
            return 0.5
        return 10.0 ** ((self.REF_RSSI - rssi) / (10.0 * self.PATH_LOSS_EXP))

class SurroundingsMapDisplay:
    """Print an ASCII occupancy grid to the console."""

    GRID_SIZE = 8
    CELL_M = 0.5  # metres per cell

    def __init__(self):
        self._grid = np.zeros((self.GRID_SIZE, self.GRID_SIZE), dtype=float)

    def update(self, vision_obstacles: list, wifi_zones: dict):
        """Merge vision obstacles and WiFi zone confidence into a grid."""
        self._grid[:] = 0.0
        mid = self.GRID_SIZE // 2

        # Vision obstacles → grid cells
        for obs in vision_obstacles:
            zone = obs.get("zone", "center") if isinstance(obs, dict) else getattr(obs, "zone", "center")
            prox = obs.get("proximity", 0.0) if isinstance(obs, dict) else getattr(obs, "proximity", 0.0)
            row = max(0, min(self.GRID_SIZE - 1, int((1.0 - prox) * self.GRID_SIZE)))
            if zone == "left":
                col = mid - 2
            elif zone == "right":
                col = mid + 1
            else:
                col = mid
            col = max(0, min(self.GRID_SIZE - 1, col))
            self._grid[row, col] = max(self._grid[row, col], min(1.0, prox * 2))

        # WiFi zone confidence → bottom half of grid
        for zone, conf in wifi_zones.items():
            if conf < 0.05:
                continue
            if zone == "left":
                c_range = range(0, mid)
            elif zone == "right":
                c_range = range(mid, self.GRID_SIZE)
            else:
                c_range = range(mid - 1, mid + 1)
            for c in c_range:
                for r in range(mid, self.GRID_SIZE):
                    self._grid[r, c] = max(self._grid[r, c], conf * 0.5)

    def render(self) -> str:
        """Return the grid as an ASCII string."""
        chars = " .oO#"
        lines = ["┌" + "──" * self.GRID_SIZE + "┐"]
        for row in self._grid:
            cells = ""
            for val in row:
                idx = min(len(chars) - 1, int(val * (len(chars) - 1)))
                cells += chars[idx] + " "
            lines.append("│" + cells + "│")
        lines.append("└" + "──" * self.GRID_SIZE + "┘")
        lines.append("  L   C   R     [rover]")
        return "\n".join(lines)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default=SERIAL_PORT if not sys.platform.startswith('win') else 'COM4')
    parser.add_argument('--show', action='store_true', help="Show video output")
    parser.add_argument('--no-wifi', action='store_true', help="Disable WiFi sensing")
    args = parser.parse_args()
    
    motor = MotorController(args.port, SERIAL_BAUD)
    motor.connect()
    
    bt = BluetoothServer()
    bt.start()

    # WiFi sensing
    wifi_sys = None
    surroundings = None
    if not args.no_wifi:
        try:
            wifi_sys = WiFiSensingSystem()
            wifi_sys.start()
            surroundings = SurroundingsMapDisplay()
            logger.info("WiFi sensing enabled")
        except Exception as exc:
            logger.warning("WiFi sensing init failed: %s", exc)
    
    if Path(YOLO_MODEL).exists():
        vision = VisionSystem(YOLO_MODEL)
    else:
        print("WARNING: YOLO model not found. Vision disabled.")
        vision = None
        
    cap = cv2.VideoCapture(CAMERA_INDEX)
    navigating = False
    last_surroundings_print = 0.0
    
    try:
        last_odom_print = time.time()
        while True:
            # Handle commands
            cmd = bt.latest_command
            if cmd:
                bt.latest_command = None
                action = cmd.get("action")
                if action == "stop":
                    navigating = False
                    motor.stop()
                    bt.send_message({"type": "speak", "text": "Stopping."})

            # Auto-navigate without phone
            if not navigating:
                navigating = True
                print("Auto-navigating towards North...")

            # Vision
            obstacles = []
            if vision and cap.isOpened():
                ret, frame = cap.read()
                if ret: 
                    obstacles = vision.detect(frame)
                    if args.show:
                        # Draw some basic debug info on frame
                        for obs in obstacles:
                            if obs['proximity'] > DANGER_DISTANCE:
                                cv2.putText(frame, f"DANGER: {obs['zone']}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
                        cv2.imshow("Netra Vision", frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break

            # WiFi sensing — collect zone confidence
            wifi_zones = {"left": 0.0, "center": 0.0, "right": 0.0}
            wifi_obstacle = False
            if wifi_sys is not None:
                wifi_zones = wifi_sys.get_zone_confidence()
                wifi_obstacle = wifi_sys.is_obstacle_detected()

            # Surroundings map
            if surroundings is not None:
                surroundings.update(obstacles, wifi_zones)
                now = time.time()
                if now - last_surroundings_print > 3.0:
                    print("\n" + surroundings.render())
                    sig_q = wifi_sys.get_signal_quality() if wifi_sys else 0.0
                    net_c = wifi_sys.get_network_count() if wifi_sys else 0
                    print(f"  WiFi: {net_c} APs  signal={sig_q:.0%}  obstacle={wifi_obstacle}")
                    last_surroundings_print = now
            
            # Logic — fuse vision + WiFi
            if navigating:
                closest = max(obstacles, key=lambda x: x['proximity']) if obstacles else None
                vision_danger = closest and closest['proximity'] > DANGER_DISTANCE
                wifi_danger = wifi_obstacle and wifi_zones.get("center", 0) > 0.3

                if vision_danger or wifi_danger:
                    motor.stop()
                    reason = "Vision" if vision_danger else "WiFi"
                    print(f"Obstacle detected ({reason}). Avoiding!")
                    bt.send_message({"type": "speak", "text": "Obstacle detected. Please wait."})
                    time.sleep(2)
                else:
                    # Going North logic using dead-reckoning heading (North = 0 rad)
                    pos = motor.get_position()
                    heading = pos["heading_rad"]
                    error = 0 - heading
                    
                    # Normalize error to [-pi, pi]
                    while error > math.pi: error -= 2*math.pi
                    while error < -math.pi: error += 2*math.pi
                    
                    # P controller for differential steering
                    base_speed = 150
                    # Modulate speed by WiFi signal quality (slow down in poor signal)
                    if wifi_sys is not None:
                        sig = wifi_sys.get_signal_quality()
                        base_speed = int(base_speed * (0.5 + 0.5 * sig))

                    turn = int(error * 100)
                    left = max(0, min(255, base_speed - turn))
                    right = max(0, min(255, base_speed + turn))
                    
                    print(f"Moving towards North... (Heading: {heading:.2f} rad, L:{left} R:{right})")
                    motor.send_command(left, right)
            else:
                motor.stop()
            
            # Send dead reckoning + WiFi status to Phone
            if time.time() - last_odom_print > 1.0:
                pos = motor.get_position()
                status_msg = {"type": "status", "odometry": pos}
                if wifi_sys is not None:
                    status_msg["wifi"] = {
                        "signal_quality": wifi_sys.get_signal_quality(),
                        "obstacle_detected": wifi_sys.is_obstacle_detected(),
                        "network_count": wifi_sys.get_network_count(),
                    }
                bt.send_message(status_msg)
                last_odom_print = time.time()
                
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        pass
    finally:
        motor.stop()
        if wifi_sys is not None:
            wifi_sys.stop()
        if args.show:
            cv2.destroyAllWindows()
        print("Exiting...")

if __name__ == "__main__":
    main()

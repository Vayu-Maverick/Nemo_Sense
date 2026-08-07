"""
rover_simulator.py — Netra Guide Rover — Full Simulator Dashboard

A rich OpenCV GUI that runs the complete rover brain on this PC for testing.
"""

from __future__ import annotations
import argparse
import json
import logging
import math
import queue
import sys
import threading
import time
import cv2
import numpy as np
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python"))

from vision import VisionSystem, VisionResult, _scan_for_webcam, SimulatedCamera
from config import (
    CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS,
    DEFAULT_SPEED, MIN_SPEED, MAX_SPEED, speed_to_pwm,
    DEPTH_DANGER_THRESHOLD, DEPTH_EMERGENCY_THRESHOLD,
    OBSTACLE_CLASS_IDS,
)

try:
    import pyttsx3
    _tts_engine = pyttsx3.init()
    _tts_engine.setProperty("rate", 160)
    _TTS_AVAILABLE = True
except Exception:
    _TTS_AVAILABLE = False

try:
    from ble_server_win import BLEServer
    _BLE_AVAILABLE = True
except Exception:
    _BLE_AVAILABLE = False

try:
    from wifi_sensing import WiFiSensingEngine, WiFiSensingResult
    from sensor_fusion import SensorFusion, FusedResult
    _WIFI_AVAILABLE = True
except ImportError:
    _WIFI_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)-15s] %(levelname)-6s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("netra.sim")

# ── Polished Cyber/Cinematic Palette ──────────────────────────────────────
C_BG       = (12, 12, 18)        # Deep Cyber Dark
C_GREEN    = (60, 240, 120)      # Neon Green
C_RED      = (60, 60, 255)       # Neon Red
C_YELLOW   = (0, 215, 255)       # Cyber Gold/Yellow
C_BLUE     = (255, 120, 0)       # Electric Blue
C_WHITE    = (250, 250, 250)
C_GREY     = (100, 100, 110)
C_TEAL     = (220, 240, 50)      # Cyan/Teal
C_PANEL    = (18, 18, 26)        # Panel background
C_ACCENT   = (45, 45, 60)        # Lines and accents

PANEL_W    = 360
FONT       = cv2.FONT_HERSHEY_DUPLEX

_tts_lock = threading.Lock()
_last_tts: dict[str, float] = {}

def speak(text: str, cooldown: float = 4.0):
    if not _TTS_AVAILABLE:
        return
    now = time.time()
    if now - _last_tts.get(text, 0) < cooldown:
        return
    _last_tts[text] = now
    def _speak():
        with _tts_lock:
            try:
                _tts_engine.say(text)
                _tts_engine.runAndWait()
            except:
                pass
    threading.Thread(target=_speak, daemon=True).start()

def _text(img, txt, pos, scale=0.5, color=C_WHITE, thick=1):
    cv2.putText(img, txt, pos, FONT, scale, color, thick, cv2.LINE_AA)

def _text_glow(img, txt, pos, scale=0.5, color=C_WHITE, thick=1):
    cv2.putText(img, txt, pos, FONT, scale, (color[0]//3, color[1]//3, color[2]//3), thick+3, cv2.LINE_AA)
    cv2.putText(img, txt, pos, FONT, scale, color, thick, cv2.LINE_AA)

def _bar(img, x, y, w, h, value, max_val, color, label):
    cv2.rectangle(img, (x, y), (x + w, y + h), C_ACCENT, -1)
    filled = int(w * min(abs(value), max_val) / max_val)
    if filled > 0:
        cv2.rectangle(img, (x, y), (x + filled, y + h), color, -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), (80, 80, 90), 1)
    _text(img, f"{label}: {value:+4.0f}", (x + 6, y + h - 5), 0.4, C_WHITE)

def _compass(img, cx, cy, radius, heading_deg, color=C_TEAL):
    cv2.circle(img, (cx, cy), radius, C_ACCENT, -1)
    cv2.circle(img, (cx, cy), radius, (80, 80, 90), 1)
    for label, angle in [("N", 0), ("E", 90), ("S", 180), ("W", 270)]:
        rad = math.radians(angle - 90)
        tx = cx + int((radius + 14) * math.cos(rad))
        ty = cy + int((radius + 14) * math.sin(rad))
        _text(img, label, (tx - 5, ty + 4), 0.35, C_GREY)
    needle_rad = math.radians(heading_deg - 90)
    nx = cx + int(radius * 0.8 * math.cos(needle_rad))
    ny = cy + int(radius * 0.8 * math.sin(needle_rad))
    cv2.arrowedLine(img, (cx, cy), (nx, ny), color, 2, tipLength=0.3)
    _text_glow(img, f"{heading_deg:.0f}", (cx - 15, cy + radius + 25), 0.45, color)

def _zone_dist_bar(img, x, y, w, h, dist_m, zone_name):
    danger = dist_m < DEPTH_DANGER_THRESHOLD
    emergency = dist_m < DEPTH_EMERGENCY_THRESHOLD
    color = C_RED if emergency else (C_YELLOW if danger else C_GREEN)
    filled = 0 if dist_m == float("inf") else int(w * max(0, 1 - dist_m / 5.0))
    cv2.rectangle(img, (x, y), (x + w, y + h), C_ACCENT, -1)
    if filled > 0:
        cv2.rectangle(img, (x + w - filled, y), (x + w, y + h), color, -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), (80,80,90), 1)
    txt = "CLEAR" if dist_m == float("inf") else f"{dist_m:.1f}m"
    _text(img, f"{zone_name}: {txt}", (x + 6, y + h - 5), 0.4, C_WHITE)

def _draw_ar_path(frame: np.ndarray, action: str):
    h, w = frame.shape[:2]
    if action == "stop":
        # Draw red X or warning overlay
        cv2.rectangle(frame, (0, 0), (w, h), (0, 0, 150), 4)
        return

    bottom_center = (w // 2, h)
    mid_center = (w // 2, int(h * 0.75))
    
    if action == "clear":
        target = (w // 2, int(h * 0.4))
        color = C_GREEN
    elif action == "steer_left":
        target = (int(w * 0.25), int(h * 0.5))
        color = C_YELLOW
    elif action == "steer_right":
        target = (int(w * 0.75), int(h * 0.5))
        color = C_YELLOW
    else:
        return
        
    t = np.linspace(0, 1, 20)
    pts_x = (1-t)**2 * bottom_center[0] + 2*(1-t)*t * mid_center[0] + t**2 * target[0]
    pts_y = (1-t)**2 * bottom_center[1] + 2*(1-t)*t * mid_center[1] + t**2 * target[1]
    
    curve_pts = np.int32(np.vstack((pts_x, pts_y)).T)
    
    # Draw path carpet (transparent polygon)
    overlay = frame.copy()
    width = 120
    left_x = pts_x - width * (1-t*0.5) 
    right_x = pts_x + width * (1-t*0.5)
    poly_pts = np.vstack((
        np.column_stack((left_x, pts_y)),
        np.column_stack((right_x[::-1], pts_y[::-1]))
    )).astype(np.int32)
    
    cv2.fillPoly(overlay, [poly_pts], color)
    cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
    
    # Draw center line glow
    cv2.polylines(frame, [curve_pts], False, color, 6, cv2.LINE_AA)
    cv2.polylines(frame, [curve_pts], False, (255, 255, 255), 2, cv2.LINE_AA)

class RoverSimulator:

    def __init__(self, no_ble: bool = False, force_sim: bool = False, port: str = "COM4"):
        self.no_ble = no_ble
        self.force_sim = force_sim
        self.port = port
        self.ser = None

        if not force_sim:
            try:
                import serial
                self.ser = serial.Serial(self.port, 115200, timeout=0.1)
                time.sleep(2.0)
                self.ser.reset_input_buffer()
                logger.info("Connected to MCU on %s", self.port)
            except Exception as e:
                logger.error("Failed to open serial port %s: %s", self.port, e)

        self.base_speed = DEFAULT_SPEED
        self.left_pwm = 0
        self.right_pwm = 0
        self.vr = VisionResult()
        self.gps: Optional[tuple[float, float]] = None
        self.heading: float = 0.0
        self.ble_connected = False
        self.ble_status = "BLE: STANDBY"
        self.frame_count = 0
        self.fps = 0.0
        self._fps_t = time.monotonic()
        self._shutdown = threading.Event()

        if force_sim:
            self.vision = VisionSystem.__new__(VisionSystem)
            self.vision.latest_ble_frame = None
            self.vision._simulated = True
            self.vision._use_onnx = False
            self.vision._use_cv2dnn = False
            self.vision._cap = SimulatedCamera(CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS)
        else:
            self.vision = VisionSystem()

        self.ble: BLEServer | None = None
        if not no_ble and _BLE_AVAILABLE:
            try:
                self.ble = BLEServer(
                    on_frame=self._on_ble_frame,
                    on_sensor=self._on_ble_sensor,
                    on_command=self._on_ble_command,
                )
                ble_thread = threading.Thread(target=self.ble.run, daemon=True)
                ble_thread.start()
                self.ble_status = "BLE: ADVERTISING"
            except Exception as exc:
                self.ble_status = f"BLE: FAILED ({exc})"
        elif not no_ble and not _BLE_AVAILABLE:
            self.ble_status = "BLE: UNAVAILABLE"

        self.wifi_engine: WiFiSensingEngine | None = None
        self.wifi_result: WiFiSensingResult | None = None
        self.sensor_fusion_engine: SensorFusion | None = None
        self.fused_result = None
        if _WIFI_AVAILABLE:
            try:
                self.wifi_engine = WiFiSensingEngine()
                self.wifi_engine.register_node("rover", "rover", "")
                self.wifi_engine.register_node("phone", "phone", "")
                self.wifi_engine.register_node("router", "router", "")
                self.sensor_fusion_engine = SensorFusion()
            except Exception as exc:
                pass

    def _on_ble_frame(self, frame: np.ndarray):
        self.vision.latest_ble_frame = frame

    def _on_ble_sensor(self, data: dict):
        gps = data.get("gps")
        if gps:
            self.gps = (gps.get("lat", 0.0), gps.get("lng", 0.0))
        self.heading = data.get("heading", self.heading)

    def _on_ble_command(self, cmd: dict):
        action = cmd.get("action", "")
        if action == "stop": self.base_speed = 0.0
        elif action == "resume": self.base_speed = DEFAULT_SPEED
        elif action == "set_speed":
            self.base_speed = max(MIN_SPEED, min(MAX_SPEED, float(cmd.get("value", DEFAULT_SPEED))))

    def _compute_motors(self, vr: VisionResult) -> tuple[int, int]:
        action = vr.recommended_action
        pwm = speed_to_pwm(self.base_speed)
        if action == "stop" or self.base_speed < 0.01:
            return 0, 0
        if action == "steer_left":
            urgency = max(0, 1 - vr.zone_min_dist["right"] / DEPTH_DANGER_THRESHOLD)
            return int(pwm * (1.0 - 0.8 * urgency)), pwm
        if action == "steer_right":
            urgency = max(0, 1 - vr.zone_min_dist["left"] / DEPTH_DANGER_THRESHOLD)
            return pwm, int(pwm * (1.0 - 0.8 * urgency))
        return pwm, pwm

    def _announce(self, vr: VisionResult):
        action = vr.recommended_action
        if action == "stop": speak("Stop! Obstacle ahead.", cooldown=3.0)
        elif action == "steer_left": speak("Steering left", cooldown=4.0)
        elif action == "steer_right": speak("Steering right", cooldown=4.0)

    def _render(self, frame: np.ndarray, vr: VisionResult) -> np.ndarray:
        cam_h, cam_w = frame.shape[:2]
        total_w = cam_w + PANEL_W
        total_h = max(cam_h, 680)
        canvas = np.full((total_h, total_w, 3), C_BG, dtype=np.uint8)

        # Draw AR Path FIRST so boxes overlay it
        _draw_ar_path(frame, vr.recommended_action)
        canvas[:cam_h, :cam_w] = frame

        for obs in vr.obstacles:
            x1, y1, x2, y2 = obs.bbox
            color = C_RED if obs.distance_m < DEPTH_EMERGENCY_THRESHOLD else (
                C_YELLOW if obs.distance_m < DEPTH_DANGER_THRESHOLD else C_GREEN
            )
            # Cyberpunk box brackets
            length = 20
            thick = 3
            cv2.line(canvas, (x1, y1), (x1+length, y1), color, thick)
            cv2.line(canvas, (x1, y1), (x1, y1+length), color, thick)
            cv2.line(canvas, (x2, y1), (x2-length, y1), color, thick)
            cv2.line(canvas, (x2, y1), (x2, y1+length), color, thick)
            cv2.line(canvas, (x1, y2), (x1+length, y2), color, thick)
            cv2.line(canvas, (x1, y2), (x1, y2-length), color, thick)
            cv2.line(canvas, (x2, y2), (x2-length, y2), color, thick)
            cv2.line(canvas, (x2, y2), (x2, y2-length), color, thick)
            
            # Subtle full box
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 1)

            lbl = f"{obs.label.upper()} {obs.distance_m:.1f}m"
            (tw, th), _ = cv2.getTextSize(lbl, FONT, 0.45, 1)
            cv2.rectangle(canvas, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
            _text(canvas, lbl, (x1 + 3, y1 - 4), 0.45, (10, 10, 10))

        # Zone dividers
        from config import ZONE_LEFT_END, ZONE_CENTER_END
        lx = int(cam_w * ZONE_LEFT_END / 320)
        cx_ = int(cam_w * ZONE_CENTER_END / 320)
        cv2.line(canvas, (lx, 0), (lx, cam_h), (255, 255, 255), 1)
        cv2.line(canvas, (cx_, 0), (cx_, cam_h), (255, 255, 255), 1)

        # Action banner
        action = vr.recommended_action
        action_colors = {"clear": C_GREEN, "stop": C_RED, "steer_left": C_YELLOW, "steer_right": C_YELLOW}
        action_labels = {"clear": "SYSTEM CLEAR // AUTO NAV", "stop": "WARNING // COLLISION IMMINENT", "steer_left": "<< STEERING LEFT", "steer_right": "STEERING RIGHT >>"}
        acolor = action_colors.get(action, C_WHITE)
        alabel = action_labels.get(action, action.upper())
        
        # Transparent banner at bottom of camera
        banner_overlay = canvas[:cam_h, :cam_w].copy()
        cv2.rectangle(banner_overlay, (0, cam_h - 40), (cam_w, cam_h), (10, 10, 15), -1)
        cv2.addWeighted(banner_overlay, 0.8, canvas[:cam_h, :cam_w], 0.2, 0, canvas[:cam_h, :cam_w])
        _text_glow(canvas, alabel, (15, cam_h - 12), 0.7, acolor, 2)

        # Top Status HUD
        src_txt = f"[{vr.source.upper()}] | {self.fps:.1f} FPS | {vr.frame_time_ms:.0f}ms INF"
        _text_glow(canvas, src_txt, (10, 22), 0.45, C_TEAL)

        # ─────────────────── RIGHT PANEL ──────────────────────────────────
        px = cam_w + 15
        
        # Panel Background
        cv2.rectangle(canvas, (cam_w, 0), (total_w, total_h), C_PANEL, -1)
        cv2.line(canvas, (cam_w, 0), (cam_w, total_h), C_ACCENT, 2)

        _text_glow(canvas, "AI HUD // NAV", (px, 35), 0.8, C_TEAL, 2)
        _text(canvas, "Autonomous Navigation System", (px, 55), 0.4, C_GREY)
        cv2.line(canvas, (cam_w+10, 65), (total_w-10, 65), C_ACCENT, 1)

        ble_color = C_GREEN if self.ble_connected else C_ORANGE
        _text(canvas, self.ble_status, (px, 90), 0.45, ble_color)
        gps_txt = (f"GPS: {self.gps[0]:.5f}, {self.gps[1]:.5f}" if self.gps else "GPS: AWAITING SIGNAL")
        _text(canvas, gps_txt, (px, 115), 0.4, C_WHITE)

        cv2.line(canvas, (cam_w+10, 130), (total_w-10, 130), C_ACCENT, 1)

        _text(canvas, "HEADING", (px, 155), 0.45, C_GREY)
        _compass(canvas, cam_w + PANEL_W // 2, 215, 48, self.heading)

        cv2.line(canvas, (cam_w+10, 280), (total_w-10, 280), C_ACCENT, 1)

        _text(canvas, "DEPTH ANALYSIS", (px, 305), 0.45, C_GREY)
        bar_w = PANEL_W - 30
        _zone_dist_bar(canvas, px, 320, bar_w, 20, vr.zone_min_dist["left"],   "PORT")
        _zone_dist_bar(canvas, px, 345, bar_w, 20, vr.zone_min_dist["center"], "BOW ")
        _zone_dist_bar(canvas, px, 370, bar_w, 20, vr.zone_min_dist["right"],  "STBD")

        cv2.line(canvas, (cam_w+10, 405), (total_w-10, 405), C_ACCENT, 1)

        _text(canvas, "MOTOR TELEMETRY", (px, 430), 0.45, C_GREY)
        _bar(canvas, px, 445, bar_w, 22, self.left_pwm,  255, C_BLUE, "DRIVE L")
        _bar(canvas, px, 475, bar_w, 22, self.right_pwm, 255, C_BLUE, "DRIVE R")

        cv2.line(canvas, (cam_w+10, 510), (total_w-10, 510), C_ACCENT, 1)

        _text(canvas, f"THROTTLE: {self.base_speed:.2f} m/s", (px, 535), 0.5, C_WHITE)
        _text(canvas, f"CYCLE: {self.frame_count}", (px, 555), 0.4, C_GREY)

        if self.wifi_result is not None:
            wifi_y = 575
            cv2.line(canvas, (cam_w+10, wifi_y), (total_w-10, wifi_y), C_ACCENT, 1)
            _text(canvas, "WIFI RADAR", (px, wifi_y + 20), 0.45, C_TEAL)
            
            q = self.wifi_result.signal_quality
            _bar(canvas, px, wifi_y + 35, bar_w, 16, q * 100, 100, C_GREEN if q > 0.6 else C_YELLOW, "SIG")
            
            if self.fused_result is not None:
                _text(canvas, f"FUSION MATCH: V:{self.fused_result.vision_confidence:.0%} W:{self.fused_result.wifi_confidence:.0%}", (px, wifi_y + 65), 0.38, C_TEAL)

        return canvas

    def run(self):
        logger.info("Starting Netra Simulator. Press Q to quit.")
        WIN = "Netra AI Dashboard // SIMULATION"
        cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WIN, CAMERA_WIDTH + PANEL_W, max(CAMERA_HEIGHT, 680))

        t_fps = time.monotonic()
        frames_since = 0

        while not self._shutdown.is_set():
            t0 = time.monotonic()
            frame, source = self.vision.capture_frame()
            if frame is None:
                frame = np.zeros((CAMERA_HEIGHT, CAMERA_WIDTH, 3), np.uint8)
                source = "none"
            display_frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT))

            vr = self.vision.process_frame(frame=display_frame.copy())
            vr.source = source
            self.vr = vr

            if self.wifi_engine is not None:
                self.wifi_result = self.wifi_engine.process()
                if self.sensor_fusion_engine is not None:
                    self.fused_result = self.sensor_fusion_engine.fuse(vr, self.wifi_result)

            self.left_pwm, self.right_pwm = self._compute_motors(vr)

            if getattr(self.vision, "_simulated", False) and hasattr(self.vision._cap, "update_physics"):
                self.vision._cap.update_physics(self.left_pwm, self.right_pwm)

            self._announce(vr)

            self.frame_count += 1
            frames_since += 1
            elapsed = time.monotonic() - t_fps
            if elapsed >= 1.0:
                self.fps = frames_since / elapsed
                frames_since = 0
                t_fps = time.monotonic()

            dashboard = self._render(display_frame, vr)
            cv2.imshow(WIN, dashboard)

            if self.ser and self.ser.is_open:
                try:
                    self.ser.write(f"MOTOR:{int(self.left_pwm)},{int(self.right_pwm)}\n".encode("ascii"))
                    self.ser.flush()
                except:
                    pass

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27): break
            elif key == ord("s"): self.base_speed = max(MIN_SPEED, self.base_speed - 0.05)
            elif key == ord("f"): self.base_speed = min(MAX_SPEED, self.base_speed + 0.05)

            elapsed = time.monotonic() - t0
            time.sleep(max(0, 0.08 - elapsed))

        cv2.destroyAllWindows()
        self.vision.release()
        if self.ble: self.ble.stop()
        logger.info("Simulator stopped.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-ble", action="store_true")
    parser.add_argument("--sim", action="store_true")
    parser.add_argument("--port", type=str, default="COM4")
    args = parser.parse_args()
    RoverSimulator(no_ble=args.no_ble, force_sim=args.sim, port=args.port).run()

if __name__ == "__main__":
    main()

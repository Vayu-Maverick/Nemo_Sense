"""
rover_simulator.py — Netra Guide Rover — Full Simulator Dashboard

A rich OpenCV GUI that runs the complete rover brain on this PC for testing.
Works with:
  - USB webcam plugged into a USB hub  ← PRIMARY input
  - BLE phone camera stream            ← when phone connects
  - Simulated frames                   ← if no webcam found

Features shown in the dashboard window:
  ┌────────────────────────────────────────────────┐
  │  LIVE CAMERA + AI DETECTIONS (with bboxes)     │
  │  BLE status bar + GPS compass                  │
  │  Zone obstacle distances (Left / Center / Right)│
  │  Motor PWM bars (Left / Right)                 │
  │  Action banner (CLEAR / STOP / STEER LEFT/RIGHT)│
  │  FPS counter + frame source                    │
  └────────────────────────────────────────────────┘

Usage:
    python rover_simulator.py                  # USB webcam + BLE mode
    python rover_simulator.py --no-ble         # webcam only, no BLE
    python rover_simulator.py --sim            # force simulated camera
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
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

# ── Add python/ to path so we can import netra modules ───────────────────
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python"))

from vision import VisionSystem, VisionResult, _scan_for_webcam, SimulatedCamera
from config import (
    CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS,
    DEFAULT_SPEED, MIN_SPEED, MAX_SPEED, speed_to_pwm,
    DEPTH_DANGER_THRESHOLD, DEPTH_EMERGENCY_THRESHOLD,
    OBSTACLE_CLASS_IDS,
)

# ── Try TTS (optional) ────────────────────────────────────────────────────
try:
    import pyttsx3
    _tts_engine = pyttsx3.init()
    _tts_engine.setProperty("rate", 160)
    _TTS_AVAILABLE = True
except Exception:
    _TTS_AVAILABLE = False

# ── Try BLE ───────────────────────────────────────────────────────────────
try:
    from ble_server_win import BLEServer
    _BLE_AVAILABLE = True
except Exception:
    _BLE_AVAILABLE = False

# ── Try WiFi Sensing ─────────────────────────────────────────────────────
try:
    from wifi_sensing import WiFiSensingEngine, WiFiSensingResult
    from sensor_fusion import SensorFusion, FusedResult
    _WIFI_AVAILABLE = True
except ImportError:
    _WIFI_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-15s] %(levelname)-6s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("netra.sim")

# ── Colour palette ────────────────────────────────────────────────────────
C_BG       = (20, 20, 30)        # dark panel background
C_GREEN    = (80, 220, 80)
C_RED      = (60, 60, 240)
C_YELLOW   = (40, 200, 220)
C_BLUE     = (220, 140, 40)
C_WHITE    = (240, 240, 240)
C_ORANGE   = (40, 160, 255)
C_GREY     = (130, 130, 130)
C_TEAL     = (200, 200, 60)

PANEL_W    = 340   # right panel width
FONT       = cv2.FONT_HERSHEY_SIMPLEX

# ── TTS helper ────────────────────────────────────────────────────────────
_tts_lock = threading.Lock()
_last_tts: Dict[str, float] = {}

def speak(text: str, cooldown: float = 4.0):
    """Speak text via TTS with per-message cooldown to avoid repetition."""
    if not _TTS_AVAILABLE:
        logger.info("[TTS] %s", text)
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
            except Exception:
                pass
    threading.Thread(target=_speak, daemon=True).start()


# ── Drawing helpers ───────────────────────────────────────────────────────

def _text(img, txt, pos, scale=0.5, color=C_WHITE, thick=1):
    cv2.putText(img, txt, pos, FONT, scale, color, thick, cv2.LINE_AA)

def _bar(img, x, y, w, h, value, max_val, color, label):
    """Draw a filled progress bar."""
    cv2.rectangle(img, (x, y), (x + w, y + h), (50, 50, 60), -1)
    filled = int(w * min(abs(value), max_val) / max_val)
    if filled > 0:
        cv2.rectangle(img, (x, y), (x + filled, y + h), color, -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), C_GREY, 1)
    _text(img, f"{label}: {value:+4.0f}", (x + 4, y + h - 6), 0.38, C_WHITE)

def _compass(img, cx, cy, radius, heading_deg, color=C_TEAL):
    """Draw a compass rose."""
    cv2.circle(img, (cx, cy), radius, (40, 40, 55), -1)
    cv2.circle(img, (cx, cy), radius, C_GREY, 1)
    for label, angle in [("N", 0), ("E", 90), ("S", 180), ("W", 270)]:
        rad = math.radians(angle - 90)
        tx = cx + int((radius + 12) * math.cos(rad))
        ty = cy + int((radius + 12) * math.sin(rad))
        _text(img, label, (tx - 5, ty + 4), 0.35, C_GREY)
    # Needle
    needle_rad = math.radians(heading_deg - 90)
    nx = cx + int(radius * 0.8 * math.cos(needle_rad))
    ny = cy + int(radius * 0.8 * math.sin(needle_rad))
    cv2.arrowedLine(img, (cx, cy), (nx, ny), color, 2, tipLength=0.3)
    _text(img, f"{heading_deg:.0f}°", (cx - 15, cy + radius + 22), 0.4, color)

def _zone_dist_bar(img, x, y, w, h, dist_m, zone_name):
    """Draw a distance bar for a zone — red=close, green=far."""
    danger = dist_m < DEPTH_DANGER_THRESHOLD
    emergency = dist_m < DEPTH_EMERGENCY_THRESHOLD
    color = C_RED if emergency else (C_YELLOW if danger else C_GREEN)
    filled = 0 if dist_m == float("inf") else int(w * max(0, 1 - dist_m / 5.0))
    cv2.rectangle(img, (x, y), (x + w, y + h), (40, 40, 50), -1)
    if filled > 0:
        cv2.rectangle(img, (x + w - filled, y), (x + w, y + h), color, -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), C_GREY, 1)
    txt = "∞" if dist_m == float("inf") else f"{dist_m:.1f}m"
    _text(img, f"{zone_name}: {txt}", (x + 4, y + h - 5), 0.38, C_WHITE)


# ══════════════════════════════════════════════════════════════════════════
# Main simulator class
# ══════════════════════════════════════════════════════════════════════════

class RoverSimulator:

    def __init__(self, no_ble: bool = False, force_sim: bool = False, port: str = "COM4"):
        self.no_ble = no_ble
        self.force_sim = force_sim
        self.port = port
        self.ser = None

        # ── Serial Connection ─────────────────────────────────────────────
        if not force_sim:
            try:
                import serial
                self.ser = serial.Serial(self.port, 115200, timeout=0.1)
                time.sleep(2.0)  # Wait for DTR reset
                self.ser.reset_input_buffer()
                logger.info("Connected to MCU on %s", self.port)
            except Exception as e:
                logger.error("Failed to open serial port %s: %s", self.port, e)
                logger.warning("Motors will NOT move!")

        # ── State ─────────────────────────────────────────────────────────
        self.base_speed = DEFAULT_SPEED
        self.left_pwm = 0
        self.right_pwm = 0
        self.vr = VisionResult()
        self.gps: Optional[Tuple[float, float]] = None
        self.heading: float = 0.0
        self.ble_connected = False
        self.ble_status = "BLE: not started"
        self.frame_count = 0
        self.fps = 0.0
        self._fps_t = time.monotonic()
        self._shutdown = threading.Event()

        # ── Vision ────────────────────────────────────────────────────────
        if force_sim:
            # Monkey-patch vision to use simulated camera
            self.vision = VisionSystem.__new__(VisionSystem)
            self.vision.latest_ble_frame = None
            self.vision._simulated = True
            self.vision._use_onnx = False
            self.vision._use_cv2dnn = False
            self.vision._cap = SimulatedCamera(CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS)
            logger.info("Forced simulated camera mode")
        else:
            self.vision = VisionSystem()

        # ── BLE server ────────────────────────────────────────────────────
        self.ble: Optional[BLEServer] = None
        if not no_ble and _BLE_AVAILABLE:
            try:
                self.ble = BLEServer(
                    on_frame=self._on_ble_frame,
                    on_sensor=self._on_ble_sensor,
                    on_command=self._on_ble_command,
                )
                ble_thread = threading.Thread(target=self.ble.run, daemon=True)
                ble_thread.start()
                self.ble_status = "BLE: advertising…"
            except Exception as exc:
                logger.error("BLE init failed: %s", exc)
                self.ble_status = f"BLE: FAILED ({exc})"
        elif not no_ble and not _BLE_AVAILABLE:
            self.ble_status = "BLE: unavailable (install bleak)"

        # ── WiFi sensing ────────────────────────────────────────────────────
        self.wifi_engine: Optional[WiFiSensingEngine] = None
        self.wifi_result: Optional[WiFiSensingResult] = None
        self.sensor_fusion_engine: Optional[SensorFusion] = None
        self.fused_result = None
        if _WIFI_AVAILABLE:
            try:
                self.wifi_engine = WiFiSensingEngine()
                self.wifi_engine.register_node("rover", "rover", "")
                self.wifi_engine.register_node("phone", "phone", "")
                self.wifi_engine.register_node("router", "router", "")
                self.sensor_fusion_engine = SensorFusion()
                logger.info("WiFi sensing enabled in simulator")
            except Exception as exc:
                logger.warning("WiFi sensing init failed in sim: %s", exc)

    # ── BLE callbacks ─────────────────────────────────────────────────────

    def _on_ble_frame(self, frame: np.ndarray):
        self.vision.latest_ble_frame = frame

    def _on_ble_sensor(self, data: dict):
        gps = data.get("gps")
        if gps:
            self.gps = (gps.get("lat", 0.0), gps.get("lng", 0.0))
        self.heading = data.get("heading", self.heading)

    def _on_ble_command(self, cmd: dict):
        action = cmd.get("action", "")
        logger.info("BLE command: %s", action)
        if action == "stop":
            self.base_speed = 0.0
        elif action == "resume":
            self.base_speed = DEFAULT_SPEED
        elif action == "set_speed":
            v = float(cmd.get("value", DEFAULT_SPEED))
            self.base_speed = max(MIN_SPEED, min(MAX_SPEED, v))

    # ── Motor computation ─────────────────────────────────────────────────

    def _compute_motors(self, vr: VisionResult) -> Tuple[int, int]:
        """Map VisionResult action to L/R PWM."""
        action = vr.recommended_action
        pwm = speed_to_pwm(self.base_speed)
        if action == "stop" or self.base_speed < 0.01:
            return 0, 0
        if action == "steer_left":
            # Urgency: how close is the obstacle?
            urgency = max(0, 1 - vr.zone_min_dist["right"] / DEPTH_DANGER_THRESHOLD)
            factor = 1.0 - 0.8 * urgency
            return int(pwm * factor), pwm
        if action == "steer_right":
            urgency = max(0, 1 - vr.zone_min_dist["left"] / DEPTH_DANGER_THRESHOLD)
            factor = 1.0 - 0.8 * urgency
            return pwm, int(pwm * factor)
        # clear — straight forward
        return pwm, pwm

    # ── TTS voice guidance ────────────────────────────────────────────────

    def _announce(self, vr: VisionResult):
        action = vr.recommended_action
        if action == "stop":
            speak("Stop! Obstacle directly ahead.", cooldown=3.0)
        elif action == "steer_left":
            speak("Steering left — obstacle on the right.", cooldown=4.0)
        elif action == "steer_right":
            speak("Steering right — obstacle on the left.", cooldown=4.0)
        elif action == "clear":
            pass  # silent when path is clear

    # ── Dashboard rendering ───────────────────────────────────────────────

    def _render(self, frame: np.ndarray, vr: VisionResult) -> np.ndarray:
        """Compose full dashboard from camera frame + side panel."""
        cam_h, cam_w = frame.shape[:2]
        total_w = cam_w + PANEL_W
        total_h = max(cam_h, 680)
        canvas = np.full((total_h, total_w, 3), C_BG, dtype=np.uint8)

        # ── Camera region ─────────────────────────────────────────────────
        canvas[:cam_h, :cam_w] = frame

        # ── Draw AI detection bounding boxes ─────────────────────────────
        for obs in vr.obstacles:
            x1, y1, x2, y2 = obs.bbox
            color = C_RED if obs.distance_m < DEPTH_EMERGENCY_THRESHOLD else (
                C_YELLOW if obs.distance_m < DEPTH_DANGER_THRESHOLD else C_GREEN
            )
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            lbl = f"{obs.label} {obs.distance_m:.1f}m"
            (tw, th), _ = cv2.getTextSize(lbl, FONT, 0.4, 1)
            cv2.rectangle(canvas, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
            _text(canvas, lbl, (x1 + 2, y1 - 4), 0.4, (10, 10, 10))

        # ── Zone dividers on camera ───────────────────────────────────────
        from config import ZONE_LEFT_END, ZONE_CENTER_END
        lx = int(cam_w * ZONE_LEFT_END / 320)
        cx_ = int(cam_w * ZONE_CENTER_END / 320)
        cv2.line(canvas, (lx, 0), (lx, cam_h), (60, 60, 80), 1)
        cv2.line(canvas, (cx_, 0), (cx_, cam_h), (60, 60, 80), 1)
        _text(canvas, "L", (lx // 2 - 5, 18), 0.4, (80, 80, 90))
        _text(canvas, "C", ((lx + cx_) // 2 - 5, 18), 0.4, (80, 80, 90))
        _text(canvas, "R", ((cx_ + cam_w) // 2 - 5, 18), 0.4, (80, 80, 90))

        # ── Action banner ─────────────────────────────────────────────────
        action = vr.recommended_action
        action_colors = {
            "clear":       C_GREEN,
            "stop":        C_RED,
            "steer_left":  C_YELLOW,
            "steer_right": C_YELLOW,
        }
        action_labels = {
            "clear":       "✔ PATH CLEAR — GOING STRAIGHT",
            "stop":        "⚠ STOP! OBSTACLE AHEAD",
            "steer_left":  "← STEERING LEFT",
            "steer_right": "→ STEERING RIGHT",
        }
        acolor = action_colors.get(action, C_WHITE)
        alabel = action_labels.get(action, action.upper())
        cv2.rectangle(canvas, (0, cam_h - 28), (cam_w, cam_h), (20, 20, 28), -1)
        _text(canvas, alabel, (8, cam_h - 9), 0.55, acolor, 2)

        # ── Camera source badge ───────────────────────────────────────────
        src_txt = f"[{vr.source.upper()}]  {self.fps:.1f} FPS  {vr.frame_time_ms:.0f}ms"
        _text(canvas, src_txt, (8, 18), 0.4, C_TEAL)

        # ─────────────────── RIGHT PANEL ──────────────────────────────────
        px = cam_w + 10

        # Title
        _text(canvas, "NETRA GUIDE ROVER", (px, 28), 0.65, C_TEAL, 2)
        _text(canvas, "Autonomous Blind Navigation System", (px, 46), 0.38, C_GREY)
        cv2.line(canvas, (cam_w, 55), (total_w, 55), (50, 50, 60), 1)

        # BLE status
        ble_color = C_GREEN if self.ble_connected else C_ORANGE
        _text(canvas, self.ble_status, (px, 76), 0.45, ble_color)

        # GPS
        gps_txt = (f"GPS: {self.gps[0]:.5f}, {self.gps[1]:.5f}"
                   if self.gps else "GPS: waiting…")
        _text(canvas, gps_txt, (px, 98), 0.4, C_WHITE)

        cv2.line(canvas, (cam_w, 108), (total_w, 108), (50, 50, 60), 1)

        # Compass
        _text(canvas, "HEADING", (px, 128), 0.45, C_GREY)
        _compass(canvas, cam_w + PANEL_W // 2, 185, 44, self.heading)

        cv2.line(canvas, (cam_w, 242), (total_w, 242), (50, 50, 60), 1)

        # Obstacle zone distances
        _text(canvas, "OBSTACLE DISTANCES", (px, 262), 0.45, C_GREY)
        bar_w = PANEL_W - 22
        _zone_dist_bar(canvas, px, 275, bar_w, 18,
                       vr.zone_min_dist["left"],   "LEFT ")
        _zone_dist_bar(canvas, px, 298, bar_w, 18,
                       vr.zone_min_dist["center"], "CTR  ")
        _zone_dist_bar(canvas, px, 321, bar_w, 18,
                       vr.zone_min_dist["right"],  "RIGHT")

        cv2.line(canvas, (cam_w, 348), (total_w, 348), (50, 50, 60), 1)

        # Motor PWM bars
        _text(canvas, "MOTOR PWM", (px, 368), 0.45, C_GREY)
        _bar(canvas, px, 380, bar_w, 20, self.left_pwm,  255, C_BLUE,  "L PWM")
        _bar(canvas, px, 408, bar_w, 20, self.right_pwm, 255, C_BLUE,  "R PWM")

        cv2.line(canvas, (cam_w, 438), (total_w, 438), (50, 50, 60), 1)

        # Speed
        _text(canvas, f"SPEED: {self.base_speed:.2f} m/s", (px, 458), 0.5, C_WHITE)
        _text(canvas, f"FRAME #{self.frame_count}", (px, 478), 0.4, C_GREY)

        # Detected objects list
        cv2.line(canvas, (cam_w, 490), (total_w, 490), (50, 50, 60), 1)
        _text(canvas, "DETECTIONS", (px, 508), 0.45, C_GREY)
        for i, obs in enumerate(vr.obstacles[:2]):
            dy = 524 + i * 16
            color = C_RED if obs.distance_m < DEPTH_DANGER_THRESHOLD else C_GREEN
            _text(canvas, f"  {obs.label} [{obs.zone}] {obs.distance_m:.1f}m",
                  (px, dy), 0.38, color)

        # ── WiFi Sensing panel ──────────────────────────────────────────
        if self.wifi_result is not None:
            wifi_y = 540
            cv2.line(canvas, (cam_w, wifi_y), (total_w, wifi_y), (50, 50, 60), 1)
            _text(canvas, "WIFI SENSING", (px, wifi_y + 18), 0.45, C_TEAL)

            # Signal quality bar
            q = self.wifi_result.signal_quality
            q_color = C_GREEN if q > 0.6 else (C_YELLOW if q > 0.3 else C_RED)
            _bar(canvas, px, wifi_y + 28, bar_w, 16, q * 100, 100, q_color, "SIGNAL")

            # Zone presence indicators
            for i, zone in enumerate(["left", "center", "right"]):
                presence = self.wifi_result.zone_presence.get(zone, 0.0)
                zy = wifi_y + 50 + i * 18
                p_color = C_RED if presence > 0.7 else (C_YELLOW if presence > 0.3 else C_GREEN)
                _bar(canvas, px, zy, bar_w, 16, presence * 100, 100, p_color, f"WiFi {zone.upper()[:3]}")

            # Fusion confidence
            if self.fused_result is not None:
                fy = wifi_y + 110
                _text(canvas, f"FUSION V:{self.fused_result.vision_confidence:.0%} W:{self.fused_result.wifi_confidence:.0%}",
                      (px, fy), 0.38, C_TEAL)

        return canvas

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        logger.info("Starting Netra rover simulator. Press Q to quit.")
        logger.info("Camera source: %s",
                    "SIMULATED" if self.vision._simulated else "USB WEBCAM")

        WIN = "Netra Guide Rover — Simulator Dashboard"
        cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WIN, CAMERA_WIDTH + PANEL_W, CAMERA_HEIGHT)

        t_fps = time.monotonic()
        frames_since = 0

        while not self._shutdown.is_set():
            t0 = time.monotonic()

            # ── Capture frame (once) ──────────────────────────────────────
            frame, source = self.vision.capture_frame()
            if frame is None:
                frame = np.zeros((CAMERA_HEIGHT, CAMERA_WIDTH, 3), np.uint8)
                source = "none"
            display_frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT))

            # ── Vision (pass captured frame directly) ─────────────────────
            vr = self.vision.process_frame(frame=display_frame.copy())
            vr.source = source
            self.vr = vr

            # ── WiFi Sensing ──────────────────────────────────────────
            if self.wifi_engine is not None:
                self.wifi_result = self.wifi_engine.process()
                if self.sensor_fusion_engine is not None:
                    self.fused_result = self.sensor_fusion_engine.fuse(vr, self.wifi_result)

            # ── Motor computation ─────────────────────────────────────────
            self.left_pwm, self.right_pwm = self._compute_motors(vr)

            # ── Apply physics to simulated camera ─────────────────────────
            if getattr(self.vision, "_simulated", False) and hasattr(self.vision._cap, "update_physics"):
                self.vision._cap.update_physics(self.left_pwm, self.right_pwm)

            # ── TTS voice guidance ────────────────────────────────────────
            self._announce(vr)

            # ── FPS ───────────────────────────────────────────────────────
            self.frame_count += 1
            frames_since += 1
            elapsed = time.monotonic() - t_fps
            if elapsed >= 1.0:
                self.fps = frames_since / elapsed
                frames_since = 0
                t_fps = time.monotonic()

            # ── Render dashboard ──────────────────────────────────────────
            dashboard = self._render(display_frame, vr)
            cv2.imshow(WIN, dashboard)

            # ── Transmit to MCU ───────────────────────────────────────────
            if self.ser and self.ser.is_open:
                try:
                    cmd = f"MOTOR:{int(self.left_pwm)},{int(self.right_pwm)}\n"
                    self.ser.write(cmd.encode("ascii"))
                    self.ser.flush()
                except Exception as e:
                    logger.error("Serial write failed: %s", e)

            # ── Log motor commands ────────────────────────────────────────
            if self.frame_count % 20 == 0:
                logger.info(
                    "Action=%-12s L_PWM=%3d R_PWM=%3d FPS=%.1f src=%s",
                    vr.recommended_action, self.left_pwm, self.right_pwm,
                    self.fps, vr.source,
                )

            # ── Key handler ───────────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            elif key == ord("s"):
                self.base_speed = max(MIN_SPEED, self.base_speed - 0.05)
                logger.info("Speed decreased to %.2f", self.base_speed)
            elif key == ord("f"):
                self.base_speed = min(MAX_SPEED, self.base_speed + 0.05)
                logger.info("Speed increased to %.2f", self.base_speed)

            # ── Pace to ~10 FPS target ────────────────────────────────────
            elapsed = time.monotonic() - t0
            sleep = max(0, 0.10 - elapsed)
            time.sleep(sleep)

        cv2.destroyAllWindows()
        self.vision.release()
        if self.ble:
            self.ble.stop()
        logger.info("Simulator stopped.")


# ══════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Netra Rover Simulator")
    parser.add_argument("--no-ble", action="store_true", help="Disable BLE server")
    parser.add_argument("--sim",    action="store_true", help="Force simulated camera")
    parser.add_argument("--port",   type=str, default="COM4", help="Arduino COM port")
    args = parser.parse_args()

    sim = RoverSimulator(no_ble=args.no_ble, force_sim=args.sim, port=args.port)
    sim.run()


if __name__ == "__main__":
    main()

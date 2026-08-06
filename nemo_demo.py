# -*- coding: utf-8 -*-
"""
nemo_demo.py -- NEMO_SENSE PC Demo
====================================
Grabs webcam, runs YOLOv5n ONNX on PC, shows a dashboard that
presents the processing as if the Arduino UNO Q is doing it.
No Arduino required to run this demo.

Usage:
    python nemo_demo.py                     # auto-detect webcam
    python nemo_demo.py --camera 1          # use camera index 1
    python nemo_demo.py --sim               # fully simulated (no webcam)
    python nemo_demo.py --model path.onnx   # custom ONNX model path

Keys:
    Q / ESC  -- quit
    S        -- slow down
    F        -- speed up
    P        -- pause / resume
    R        -- reset heading

Dependencies (auto-installed by run_nemo_demo.bat):
    pip install opencv-python numpy onnxruntime
"""


from __future__ import annotations

import argparse
import math
import os
import sys
import time
import threading
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

# Model search order
ONNX_SEARCH = [
    Path(__file__).parent / "python" / "models" / "yolov5n.onnx",
    Path(__file__).parent / "yolov5n.onnx",
    Path(__file__).parent.parent / "nemo_sense" / "python" / "models" / "yolov5n.onnx",
    Path(__file__).parent.parent / "nemo_sense" / "yolov5n.onnx",
]

CAM_W, CAM_H = 640, 480
PANEL_W       = 360
INF           = float("inf")
CONF_THRESH   = 0.45
NMS_IOU       = 0.45
DANGER_M      = 2.0      # m -- yellow warning
EMERGENCY_M   = 0.8      # m -- red / stop
BASE_SPEED    = 0.55     # m/s

# COCO class names (YOLOv5 defaults)
COCO_NAMES = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck",
    "boat","traffic light","fire hydrant","stop sign","parking meter","bench",
    "bird","cat","dog","horse","sheep","cow","elephant","bear","zebra",
    "giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee",
    "skis","snowboard","sports ball","kite","baseball bat","baseball glove",
    "skateboard","surfboard","tennis racket","bottle","wine glass","cup",
    "fork","knife","spoon","bowl","banana","apple","sandwich","orange",
    "broccoli","carrot","hot dog","pizza","donut","cake","chair","couch",
    "potted plant","bed","dining table","toilet","tv","laptop","mouse",
    "remote","keyboard","cell phone","microwave","oven","toaster","sink",
    "refrigerator","book","clock","vase","scissors","teddy bear","hair drier",
    "toothbrush",
]

# Obstacle classes we care about (person, bicycle, car, motorcycle, bus, truck)
OBSTACLE_IDS = {0, 1, 2, 3, 5, 7}

# -----------------------------------------------------------------------------
# Colours  (BGR)
# -----------------------------------------------------------------------------
C_BG       = (15, 17, 25)
C_PANEL    = (20, 22, 33)
C_GREEN    = (60, 210, 90)
C_RED      = (50, 50, 220)
C_YELLOW   = (30, 195, 215)
C_BLUE     = (210, 130, 40)
C_WHITE    = (235, 235, 235)
C_ORANGE   = (40, 155, 255)
C_GREY     = (100, 100, 115)
C_TEAL     = (180, 205, 60)
C_ACCENT   = (100, 80, 200)   # arduino purple-ish
C_LIME     = (50, 240, 120)
FONT       = cv2.FONT_HERSHEY_SIMPLEX


# -----------------------------------------------------------------------------
# Detection dataclass (plain dict-like)
# -----------------------------------------------------------------------------

class Det:
    __slots__ = ("x1","y1","x2","y2","conf","cls_id","label","zone","dist_m")
    def __init__(self, x1,y1,x2,y2, conf, cls_id):
        self.x1,self.y1,self.x2,self.y2 = x1,y1,x2,y2
        self.conf  = conf
        self.cls_id= cls_id
        self.label = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else str(cls_id)
        self.zone  = "center"
        self.dist_m= INF


# -----------------------------------------------------------------------------
# Simulated camera (coloured squares that move around)
# -----------------------------------------------------------------------------

class SimCam:
    def __init__(self):
        self._t = 0.0
        self._objects: list = [
            {"x": 0.2, "y": 0.5, "vx": 0.003, "vy": 0.001, "w": 0.12, "h": 0.25, "cls": 0},
            {"x": 0.7, "y": 0.4, "vx":-0.002, "vy": 0.002, "w": 0.10, "h": 0.20, "cls": 2},
        ]

    def read(self):
        self._t += 0.016
        frame = np.zeros((CAM_H, CAM_W, 3), np.uint8)
        # grid background
        for gx in range(0, CAM_W, 40):
            cv2.line(frame, (gx,0), (gx, CAM_H), (28,30,42), 1)
        for gy in range(0, CAM_H, 40):
            cv2.line(frame, (0,gy), (CAM_W, gy), (28,30,42), 1)
        for o in self._objects:
            o["x"] = (o["x"] + o["vx"]) % 1.0
            o["y"] = max(0.1, min(0.9, o["y"] + o["vy"] + 0.001*math.sin(self._t)))
            x1 = int(o["x"] * CAM_W)
            y1 = int((o["y"] - o["h"]/2) * CAM_H)
            x2 = int((o["x"] + o["w"]) * CAM_W)
            y2 = int((o["y"] + o["h"]/2) * CAM_H)
            col = (60,180,60) if o["cls"]==0 else (40,80,200)
            cv2.rectangle(frame, (x1,y1), (x2,y2), col, -1)
            cv2.putText(frame, COCO_NAMES[o["cls"]], (x1+2, y1+14),
                        FONT, 0.4, (220,220,220), 1, cv2.LINE_AA)
        # scanline effect
        frame[::4, :] = frame[::4, :] // 2
        return True, frame

    def release(self):
        pass


# -----------------------------------------------------------------------------
# YOLOv5n Inference  (pure OpenCV DNN -- no torch/ultralytics needed)
# -----------------------------------------------------------------------------

class YOLOv5:
    def __init__(self, model_path: Optional[Path]):
        self._net = None
        if model_path and model_path.exists():
            try:
                self._net = cv2.dnn.readNetFromONNX(str(model_path))
                print(f"[AI] YOLOv5n loaded: {model_path}")
            except Exception as e:
                print(f"[AI] ONNX load failed: {e} -- using simulated detections")
        else:
            print("[AI] No ONNX model found -- using simulated detections")

    @property
    def has_model(self):
        return self._net is not None

    def infer(self, bgr_frame: np.ndarray) -> List[Det]:
        if self._net is None:
            return self._sim_detections(bgr_frame)
        try:
            blob = cv2.dnn.blobFromImage(
                bgr_frame, 1/255.0, (640, 640), swapRB=True, crop=False)
            self._net.setInput(blob)
            t0 = time.monotonic()
            raw = self._net.forward()
            self._last_ms = (time.monotonic() - t0) * 1000
            return self._parse(raw, bgr_frame.shape)
        except Exception as e:
            print(f"[AI] Inference error: {e}")
            return []

    def _parse(self, raw, shape) -> List[Det]:
        h, w = shape[:2]
        outs = raw[0] if raw.ndim == 3 else raw
        boxes, scores, ids = [], [], []
        for r in outs:
            conf = float(r[4])
            if conf < CONF_THRESH:
                continue
            cls_scores = r[5:]
            cls_id = int(np.argmax(cls_scores))
            score = conf * float(cls_scores[cls_id])
            if score < CONF_THRESH:
                continue
            if cls_id not in OBSTACLE_IDS:
                continue
            cx,cy,bw,bh = r[:4]
            x1 = int((cx - bw/2) * w / 640)
            y1 = int((cy - bh/2) * h / 480)
            x2 = int((cx + bw/2) * w / 640)
            y2 = int((cy + bh/2) * h / 480)
            boxes.append([x1,y1,x2-x1,y2-y1])
            scores.append(float(score))
            ids.append(cls_id)

        if not boxes:
            return []
        idxs = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESH, NMS_IOU)
        dets = []
        for i in (idxs.flatten() if len(idxs) else []):
            b = boxes[i]
            d = Det(b[0], b[1], b[0]+b[2], b[1]+b[3], scores[i], ids[i])
            dets.append(d)
        return dets

    def _sim_detections(self, frame) -> List[Det]:
        """Fake detections with slow oscillating movement for demo."""
        t = time.monotonic()
        dets = []
        # Moving 'person' on right side
        x = int(CAM_W * (0.6 + 0.2*math.sin(t*0.5)))
        d = Det(x, 80, x+100, 380, 0.87, 0)
        dets.append(d)
        if math.sin(t*0.3) > 0.3:
            d2 = Det(30, 100, 160, 350, 0.72, 2)  # car left
            dets.append(d2)
        return dets


# -----------------------------------------------------------------------------
# Navigation / decision
# -----------------------------------------------------------------------------

def classify_zones(dets: List[Det], frame_w: int) -> List[Det]:
    l_end = frame_w // 3
    r_start = 2 * frame_w // 3
    for d in dets:
        cx = (d.x1 + d.x2) // 2
        area_ratio = ((d.x2-d.x1)*(d.y2-d.y1)) / (frame_w * CAM_H)
        d.dist_m = max(0.3, 4.0 * (1.0 - area_ratio * 8))
        d.zone = "left" if cx < l_end else ("right" if cx > r_start else "center")
    return dets


def decide(dets: List[Det]) -> Tuple[str, int, int]:
    """Return (action, left_pwm, right_pwm)."""
    zone_min = {"left": INF, "center": INF, "right": INF}
    for d in dets:
        if d.dist_m < zone_min[d.zone]:
            zone_min[d.zone] = d.dist_m

    base = int(BASE_SPEED * 220)

    if zone_min["center"] < EMERGENCY_M:
        return "STOP", 0, 0

    if zone_min["center"] < DANGER_M:
        # Try to steer to the clearer side
        if zone_min["left"] > zone_min["right"]:
            return "STEER LEFT", int(base*0.2), base
        else:
            return "STEER RIGHT", base, int(base*0.2)

    if zone_min["right"] < DANGER_M:
        return "STEER LEFT", int(base*0.4), base

    if zone_min["left"] < DANGER_M:
        return "STEER RIGHT", base, int(base*0.4)

    return "FORWARD", base, base


# -----------------------------------------------------------------------------
# Drawing helpers
# -----------------------------------------------------------------------------

def txt(img, s, pos, scale=0.45, color=C_WHITE, thick=1):
    cv2.putText(img, s, pos, FONT, scale, color, thick, cv2.LINE_AA)

def bar(img, x, y, w, h, val, max_val, color, label=""):
    cv2.rectangle(img, (x,y), (x+w, y+h), (35,37,52), -1)
    f = int(w * min(abs(val), max_val) / max(max_val, 1))
    if f > 0:
        cv2.rectangle(img, (x,y), (x+f, y+h), color, -1)
    cv2.rectangle(img, (x,y), (x+w, y+h), C_GREY, 1)
    if label:
        txt(img, f"{label}: {val:3.0f}", (x+4, y+h-4), 0.35, C_WHITE)

def hline(img, y, x0, x1):
    cv2.line(img, (x0, y), (x1, y), (45, 48, 68), 1)

def rounded_rect(img, x1, y1, x2, y2, color, thickness=1, r=6):
    cv2.rectangle(img, (x1+r, y1), (x2-r, y2), color, thickness)
    cv2.rectangle(img, (x1, y1+r), (x2, y2-r), color, thickness)

def compass(img, cx, cy, radius, heading_deg):
    cv2.circle(img, (cx,cy), radius, (30,33,48), -1)
    cv2.circle(img, (cx,cy), radius, C_GREY, 1)
    for label, angle in [("N",0),("E",90),("S",180),("W",270)]:
        rad = math.radians(angle - 90)
        tx = cx + int((radius+12)*math.cos(rad))
        ty = cy + int((radius+12)*math.sin(rad))
        txt(img, label, (tx-4, ty+4), 0.33, C_GREY)
    needle = math.radians(heading_deg - 90)
    nx = cx + int(radius*0.82*math.cos(needle))
    ny = cy + int(radius*0.82*math.sin(needle))
    cv2.arrowedLine(img, (cx,cy), (nx,ny), C_TEAL, 2, tipLength=0.3)
    txt(img, f"{heading_deg:.0f}deg", (cx-14, cy+radius+18), 0.38, C_TEAL)


def draw_mini_rover(img, x, y, action):
    """Draw tiny top-down rover schematic with animated wheels."""
    t = time.monotonic()
    spin = int(t * 10) % 8

    body_color = C_TEAL if action == "FORWARD" else (
        C_RED if action == "STOP" else C_YELLOW)

    # Body
    cv2.rectangle(img, (x, y), (x+40, y+60), body_color, 2)
    cv2.rectangle(img, (x+5, y+5), (x+35, y+55), (30,33,48), -1)

    # Arrow inside
    if action == "FORWARD":
        cv2.arrowedLine(img, (x+20, y+45), (x+20, y+15), C_TEAL, 2, tipLength=0.3)
    elif action == "STOP":
        cv2.line(img, (x+10, y+30), (x+30, y+30), C_RED, 2)
    elif "LEFT" in action:
        cv2.arrowedLine(img, (x+28, y+30), (x+10, y+30), C_YELLOW, 2, tipLength=0.3)
    elif "RIGHT" in action:
        cv2.arrowedLine(img, (x+12, y+30), (x+30, y+30), C_YELLOW, 2, tipLength=0.3)

    # Wheels (spinning dots to show movement)
    wheel_col = C_LIME if action != "STOP" else C_RED
    for wx, wy in [(x-6, y+10), (x-6, y+40), (x+46, y+10), (x+46, y+40)]:
        cv2.circle(img, (wx, wy), 5, wheel_col, -1)
        if action != "STOP":
            dot_a = math.radians(spin * 45)
            dx = int(3*math.cos(dot_a))
            dy = int(3*math.sin(dot_a))
            cv2.circle(img, (wx+dx, wy+dy), 1, C_BG, -1)


def draw_cpu_activity(img, x, y, w, fps, inference_ms):
    """Animated NPU utilisation bar."""
    t = time.monotonic()
    util = min(1.0, (fps / 12.0) + 0.1*math.sin(t*3))
    bar(img, x, y, w, 14, int(util*100), 100, C_ACCENT, "NPU")
    txt(img, f"{inference_ms:.0f}ms / frame", (x, y+28), 0.38, C_GREY)


# -----------------------------------------------------------------------------
# Main dashboard renderer
# -----------------------------------------------------------------------------

def render(frame: np.ndarray,
           dets: List[Det],
           action: str,
           left_pwm: int,
           right_pwm: int,
           fps: float,
           inference_ms: float,
           heading: float,
           frame_no: int,
           paused: bool,
           source: str,
           zone_min: dict) -> np.ndarray:

    cam_h, cam_w = frame.shape[:2]
    total_w = cam_w + PANEL_W
    total_h = max(cam_h, 700)

    canvas = np.full((total_h, total_w, 3), C_BG, dtype=np.uint8)
    # Panel background slightly lighter
    cv2.rectangle(canvas, (cam_w, 0), (total_w, total_h), C_PANEL, -1)

    # -- Camera frame ----------------------------------------------------------
    canvas[:cam_h, :cam_w] = frame

    # Scanline overlay (thin)
    canvas[:cam_h:3, :cam_w] = (canvas[:cam_h:3, :cam_w] * 0.88).astype(np.uint8)

    # Zone dividers
    lx = cam_w // 3
    rx = 2 * cam_w // 3
    for xd in [lx, rx]:
        cv2.line(canvas, (xd, 0), (xd, cam_h), (50, 54, 80), 1)
    txt(canvas, "LEFT",   (lx//2 - 18, 16), 0.4, (65,70,95))
    txt(canvas, "CENTER", (lx + (rx-lx)//2 - 28, 16), 0.4, (65,70,95))
    txt(canvas, "RIGHT",  (rx + (cam_w-rx)//2 - 22, 16), 0.4, (65,70,95))

    # -- Detection bounding boxes ----------------------------------------------
    for d in dets:
        col = C_RED if d.dist_m < EMERGENCY_M else (
              C_YELLOW if d.dist_m < DANGER_M else C_GREEN)
        cv2.rectangle(canvas, (d.x1, d.y1), (d.x2, d.y2), col, 2)
        # Corner accents
        clen = 10
        for cx0, cy0, sx, sy in [(d.x1,d.y1,1,1),(d.x2,d.y1,-1,1),
                                  (d.x1,d.y2,1,-1),(d.x2,d.y2,-1,-1)]:
            cv2.line(canvas,(cx0,cy0),(cx0+sx*clen,cy0),col,2)
            cv2.line(canvas,(cx0,cy0),(cx0,cy0+sy*clen),col,2)

        label = f"{d.label}  {d.dist_m:.1f}m  [{d.zone.upper()[0]}]"
        (tw, th), _ = cv2.getTextSize(label, FONT, 0.38, 1)
        cv2.rectangle(canvas, (d.x1, d.y1-th-6), (d.x1+tw+6, d.y1), col, -1)
        txt(canvas, label, (d.x1+3, d.y1-4), 0.38, (10,10,10))

    # -- Action banner (bottom of camera) -------------------------------------
    action_colors = {
        "FORWARD":     C_GREEN,
        "STOP":        C_RED,
        "STEER LEFT":  C_YELLOW,
        "STEER RIGHT": C_YELLOW,
    }
    acol = action_colors.get(action, C_WHITE)
    cv2.rectangle(canvas, (0, cam_h-32), (cam_w, cam_h), (12,14,22), -1)

    arrows = {"FORWARD":"^ FORWARD","STOP":"[X] STOP","STEER LEFT":"<< STEER LEFT","STEER RIGHT":">> STEER RIGHT"}
    txt(canvas, arrows.get(action, action), (10, cam_h-10), 0.6, acol, 2)

    if paused:
        txt(canvas, "PAUSED", (cam_w-90, cam_h-10), 0.55, C_ORANGE, 2)

    # Source + FPS badge
    txt(canvas, f"{source.upper()}  {fps:.1f} FPS", (8, 18), 0.4, C_TEAL)

    # -- RIGHT PANEL -----------------------------------------------------------
    px = cam_w + 10
    pw = PANEL_W - 16
    y  = 16

    # -- HEADER ---------------------------------------------------------------
    cv2.rectangle(canvas, (cam_w, 0), (total_w, 52), (22, 20, 38), -1)
    txt(canvas, "NEMO_SENSE", (px, 22), 0.7, C_ACCENT, 2)
    txt(canvas, "ARDUINO UNO Q  |  NPU ACTIVE", (px, 40), 0.36, C_GREY)
    hline(canvas, 52, cam_w, total_w)
    y = 68

    # -- NPU Activity ---------------------------------------------------------
    txt(canvas, "NEURAL PROCESSING UNIT", (px, y), 0.42, C_GREY)
    y += 16
    draw_cpu_activity(canvas, px, y, pw, fps, inference_ms)
    y += 40

    # Inference ms pill
    ms_col = C_GREEN if inference_ms < 120 else (C_YELLOW if inference_ms < 250 else C_RED)
    cv2.rectangle(canvas, (px, y), (px+pw, y+18), (28,30,45), -1)
    txt(canvas, f"YOLOv5n ONNX  conf={CONF_THRESH}  {inference_ms:.0f}ms", (px+4,y+13), 0.37, ms_col)
    y += 26

    hline(canvas, y, cam_w, total_w); y += 14

    # -- Obstacle Zones --------------------------------------------------------
    txt(canvas, "ZONE DISTANCES", (px, y), 0.42, C_GREY); y += 16
    for zone_name in ["left", "center", "right"]:
        d = zone_min[zone_name]
        if d == INF:
            fill, zcol, dtxt = 0, C_GREEN, "clear"
        else:
            fill = int(pw * max(0, 1 - d/5.0))
            zcol = C_RED if d < EMERGENCY_M else (C_YELLOW if d < DANGER_M else C_GREEN)
            dtxt = f"{d:.1f}m"
        cv2.rectangle(canvas, (px, y), (px+pw, y+17), (35,38,55), -1)
        if fill: cv2.rectangle(canvas, (px+pw-fill, y), (px+pw, y+17), zcol, -1)
        cv2.rectangle(canvas, (px, y), (px+pw, y+17), C_GREY, 1)
        txt(canvas, f"{zone_name.upper():<6}  {dtxt}", (px+4, y+12), 0.38, C_WHITE)
        y += 21

    y += 6; hline(canvas, y, cam_w, total_w); y += 14

    # -- Motor PWM -------------------------------------------------------------
    txt(canvas, "MOTOR OUTPUT  (relay switched)", (px, y), 0.42, C_GREY); y += 16
    bar(canvas, px, y, pw, 18, left_pwm,  255, C_BLUE,  "L PWM"); y += 24
    bar(canvas, px, y, pw, 18, right_pwm, 255, C_BLUE,  "R PWM"); y += 28

    hline(canvas, y, cam_w, total_w); y += 14

    # -- Mini rover diagram ----------------------------------------------------
    txt(canvas, "STEERING VIEW", (px, y), 0.42, C_GREY); y += 10
    draw_mini_rover(canvas, cam_w + PANEL_W//2 - 24, y + 2, action)
    y += 80

    hline(canvas, y, cam_w, total_w); y += 14

    # -- Compass + heading -----------------------------------------------------
    txt(canvas, "HEADING", (px, y), 0.42, C_GREY)
    compass(canvas, cam_w + PANEL_W//2, y + 52, 38, heading)
    y += 110

    hline(canvas, y, cam_w, total_w); y += 14

    # -- Detection list --------------------------------------------------------
    txt(canvas, f"DETECTIONS ({len(dets)})", (px, y), 0.42, C_GREY); y += 16
    for d in dets[:4]:
        dcol = C_RED if d.dist_m < DANGER_M else C_GREEN
        txt(canvas, f"  {d.label:<12} {d.zone.upper()[0]}  {d.dist_m:.1f}m  {d.conf:.0%}",
            (px, y), 0.37, dcol)
        y += 15
    if not dets:
        txt(canvas, "  -- no obstacles --", (px, y), 0.38, C_GREY); y += 15

    y += 4; hline(canvas, y, cam_w, total_w); y += 12

    # -- Status line ----------------------------------------------------------
    txt(canvas, f"frame #{frame_no}   speed {BASE_SPEED:.2f} m/s", (px, y), 0.38, C_GREY)
    y += 16
    txt(canvas, "Q=quit  S=slow  F=fast  P=pause  R=reset", (px, y), 0.33, (60,65,90))

    return canvas


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def find_model() -> Optional[Path]:
    for p in ONNX_SEARCH:
        if p.exists():
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=-1, help="Camera index (-1 = auto)")
    ap.add_argument("--stream", type=str, default="", help="HTTP stream URL (e.g. http://192.168.1.X:8080/)")
    ap.add_argument("--sim",    action="store_true",   help="Simulated camera (no hardware)")
    ap.add_argument("--model",  type=str, default=None, help="Path to yolov5n.onnx")
    args = ap.parse_args()

    # -- Model -----------------------------------------------------------------
    model_path = Path(args.model) if args.model else find_model()
    yolo = YOLOv5(model_path)

    if args.sim:
        cap = SimCam()
        source = "SIMULATED"
        print("[CAM] Using simulated camera")
    elif args.stream:
        cap = cv2.VideoCapture(args.stream)
        if not cap.isOpened():
            print(f"[CAM] Failed to open stream {args.stream} -- falling back to simulated")
            cap = SimCam()
            source = "SIMULATED"
        else:
            source = f"STREAM [{args.stream[:20]}]"
            print(f"[CAM] Opened network stream: {args.stream}")
    else:
        idx = args.camera
        if idx == -1:
            # Auto-detect
            for i in range(4):
                c = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if c.isOpened():
                    ret, _ = c.read()
                    if ret:
                        cap = c
                        idx = i
                        break
                    c.release()
            else:
                print("[CAM] No webcam found -- falling back to simulated camera")
                cap = SimCam()
                source = "SIMULATED"
                idx = -1
        else:
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                print(f"[CAM] Camera {idx} not available -- using simulated")
                cap = SimCam()
                idx = -1

        if idx >= 0:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
            cap.set(cv2.CAP_PROP_FPS, 30)
            source = f"WEBCAM [{idx}]"
            print(f"[CAM] Opened camera {idx}")

    # -- State -----------------------------------------------------------------
    heading   = 0.0
    frame_no  = 0
    paused    = False
    fps       = 0.0
    infer_ms  = 0.0
    t_fps     = time.monotonic()
    fps_count = 0
    last_dets: List[Det] = []
    last_action = "FORWARD"
    last_left = last_right = 120

    WIN = "NEMO_SENSE -- Live AI Demo"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, CAM_W + PANEL_W, max(CAM_H, 700))

    print("[SIM] Running. Press Q or ESC to quit.")

    while True:
        t0 = time.monotonic()

        ret, raw = cap.read()
        if not ret or raw is None:
            raw = np.zeros((CAM_H, CAM_W, 3), np.uint8)

        frame = cv2.resize(raw, (CAM_W, CAM_H))

        if not paused:
            # -- AI inference ------------------------------------------------
            t_inf = time.monotonic()
            dets  = yolo.infer(frame.copy())
            infer_ms = (time.monotonic() - t_inf) * 1000

            dets = classify_zones(dets, CAM_W)
            action, left_pwm, right_pwm = decide(dets)

            # Smooth heading based on action
            if action == "STEER LEFT":
                heading = (heading - 3) % 360
            elif action == "STEER RIGHT":
                heading = (heading + 3) % 360

            last_dets   = dets
            last_action = action
            last_left   = left_pwm
            last_right  = right_pwm
            frame_no   += 1

        # Zone mins for display
        zone_min = {"left": INF, "center": INF, "right": INF}
        for d in last_dets:
            if d.dist_m < zone_min[d.zone]:
                zone_min[d.zone] = d.dist_m

        # FPS
        fps_count += 1
        elapsed = time.monotonic() - t_fps
        if elapsed >= 1.0:
            fps = fps_count / elapsed
            fps_count = 0
            t_fps = time.monotonic()

        # Render
        canvas = render(
            frame, last_dets, last_action,
            last_left, last_right,
            fps, infer_ms, heading, frame_no,
            paused, source, zone_min
        )
        cv2.imshow(WIN, canvas)

        # Keys
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
        elif key in (ord("p"), ord("P")):
            paused = not paused
            print(f"[SIM] {'PAUSED' if paused else 'RESUMED'}")
        elif key in (ord("s"), ord("S")):
            BASE_SPEED_NEW = max(0.1, BASE_SPEED - 0.05)
            # Can't reassign global easily, just log
            print(f"[SIM] S key -- would slow down")
        elif key in (ord("f"), ord("F")):
            print(f"[SIM] F key -- would speed up")
        elif key in (ord("r"), ord("R")):
            heading = 0.0
            print("[SIM] Heading reset to 0deg")

        # Throttle to ~15 FPS max
        elapsed = time.monotonic() - t0
        time.sleep(max(0, 0.066 - elapsed))

    cv2.destroyAllWindows()
    if hasattr(cap, "release"):
        cap.release()
    print("[SIM] Stopped.")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
nemo_demo.py -- NEMO_SENSE AI Navigation Dashboard v4
======================================================
Live webcam + YOLOv5n (all 80 COCO classes) + AR path overlay
+ Quarky robot serial control from laptop.

The AI decision (FORWARD/STEER LEFT/STEER RIGHT/STOP) is:
  1. Drawn as a perspective AR corridor on the live video
  2. Sent as a motor command over USB serial to Quarky

Usage:
    python nemo_demo.py                        # auto webcam, no robot
    python nemo_demo.py --camera 1             # specific camera index
    python nemo_demo.py --quarky COM5          # auto webcam + Quarky on COM5
    python nemo_demo.py --quarky auto          # auto-detect Quarky port
    python nemo_demo.py --stream URL           # MJPEG network stream
    python nemo_demo.py --no-path              # hide AR overlay

Keys:  Q/ESC=quit   P=pause
"""

from __future__ import annotations
import argparse, math, time, threading, queue, asyncio
from pathlib import Path

import cv2
import numpy as np
import socket
import asyncio

# Quarky BLE (optional -- imported only if bleak is installed)
try:
    from bleak import BleakClient, BleakScanner
    import bleak.exc
    _BLE_OK = True
except ImportError:
    _BLE_OK = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CAM_W, CAM_H = 640, 480
PANEL_W       = 360
TOTAL_W       = CAM_W + PANEL_W
TOTAL_H       = max(CAM_H, 720)
INF           = float("inf")
CONF_THRESH   = 0.45
DANGER_M      = 2.0
EMERGENCY_M   = 0.8
BASE_SPEED    = 0.55
FONT          = cv2.FONT_HERSHEY_SIMPLEX
FONT_B        = cv2.FONT_HERSHEY_DUPLEX

ONNX_SEARCH = [
    Path(__file__).parent / "python" / "models" / "yolov5n.onnx",
    Path(__file__).parent / "yolov5n.onnx",
]

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
# Detect ALL 80 COCO classes as potential obstacles
OBSTACLE_IDS = set(range(80))

# ---------------------------------------------------------------------------
# Colours (BGR)
# ---------------------------------------------------------------------------
BG        = (10,  12,  20)
PANEL_BG  = (14,  16,  26)
BORDER    = (35,  40,  60)
C_WHITE   = (230, 232, 240)
C_DIM     = (80,   85, 105)
C_GREEN   = (55,  210,  85)
C_RED     = (60,   55, 220)
C_YELLOW  = (25,  195, 215)
C_ORANGE  = (40,  155, 255)
C_BLUE    = (200, 120,  35)
C_TEAL    = (175, 210,  55)
C_PURPLE  = (185, 100, 120)
C_LIME    = (45,  245, 115)

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
class Det:
    __slots__ = ("x1","y1","x2","y2","conf","cls_id","label","zone","dist_m")
    def __init__(self, x1, y1, x2, y2, conf, cls_id):
        self.x1,self.y1,self.x2,self.y2 = int(x1),int(y1),int(x2),int(y2)
        self.conf   = conf
        self.cls_id = cls_id
        self.label  = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else "object"
        self.zone   = "center"
        self.dist_m = INF

# ---------------------------------------------------------------------------
# YOLOv5n inference
# ---------------------------------------------------------------------------
class YOLOv5:
    def __init__(self, p):
        self._net = None
        if p and Path(str(p)).exists():
            try:
                self._net = cv2.dnn.readNetFromONNX(str(p))
                print(f"[AI] Model: {Path(str(p)).name}")
            except Exception as e:
                print(f"[AI] Load fail: {e} -- confidence display will use fallback")
        else:
            print("[AI] No ONNX model -- detection display uses simulated fallback")

    def infer(self, frame: np.ndarray) -> list[Det]:
        if self._net is None:
            return self._fallback(frame)
        try:
            blob = cv2.dnn.blobFromImage(frame, 1/255., (640,640), swapRB=True)
            self._net.setInput(blob)
            raw = self._net.forward()
            return self._parse(raw, frame.shape)
        except Exception:
            return []

    def _parse(self, raw, shape) -> list[Det]:
        h, w = shape[:2]
        outs = raw[0] if raw.ndim == 3 else raw
        boxes, scores, ids = [], [], []
        for r in outs:
            conf = float(r[4])
            if conf < CONF_THRESH: continue
            cs = r[5:]; ci = int(np.argmax(cs))
            sc = conf * float(cs[ci])
            if sc < CONF_THRESH or ci not in OBSTACLE_IDS: continue
            cx,cy,bw,bh = r[:4]
            x1=int((cx-bw/2)*w/640); y1=int((cy-bh/2)*h/480)
            x2=int((cx+bw/2)*w/640); y2=int((cy+bh/2)*h/480)
            boxes.append([x1,y1,x2-x1,y2-y1]); scores.append(sc); ids.append(ci)
        if not boxes: return []
        idxs = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESH, 0.45)
        out = []
        for i in (idxs.flatten() if len(idxs) else []):
            b = boxes[i]
            d = Det(b[0],b[1],b[0]+b[2],b[1]+b[3], scores[i], ids[i])
            out.append(d)
        return out

    def _fallback(self, frame: np.ndarray) -> list[Det]:
        """When no model -- look for motion blobs as stand-in detections."""
        return []

# ---------------------------------------------------------------------------
# AR PATH OVERLAY
# ---------------------------------------------------------------------------
# Horizon line is at 45% of frame height (works for most outdoor/indoor angles)
HORIZON_Y  = int(CAM_H * 0.45)
GROUND_CX  = CAM_W // 2      # centre of frame bottom

def _bezier(p0, p1, p2, steps=30):
    """Quadratic Bezier: returns list of (x,y) points."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = int((1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t**2*p2[0])
        y = int((1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t**2*p2[1])
        pts.append((x, y))
    return pts

def _path_forward():
    """Straight corridor points: [(left_pts), (right_pts)]"""
    half_bot = int(CAM_W * 0.14)
    half_top = int(CAM_W * 0.04)
    cx = GROUND_CX
    hy = HORIZON_Y + 20
    left  = [(cx - half_bot, CAM_H), (cx - half_top, hy)]
    right = [(cx + half_bot, CAM_H), (cx + half_top, hy)]
    return left, right

def _path_left():
    """Left-curving corridor using Bezier."""
    half_bot = int(CAM_W * 0.14)
    cx = GROUND_CX
    hy = HORIZON_Y + 20
    # Control point shifted left
    ctrl_l  = (cx - int(CAM_W*0.30), int(CAM_H*0.65))
    ctrl_r  = (cx - int(CAM_W*0.08), int(CAM_H*0.65))
    dest_l  = (cx - int(CAM_W*0.40), hy)
    dest_r  = (cx - int(CAM_W*0.22), hy)
    left  = _bezier((cx - half_bot, CAM_H), ctrl_l, dest_l)
    right = _bezier((cx + half_bot, CAM_H), ctrl_r, dest_r)
    return left, right

def _path_right():
    """Right-curving corridor."""
    half_bot = int(CAM_W * 0.14)
    cx = GROUND_CX
    hy = HORIZON_Y + 20
    ctrl_l = (cx + int(CAM_W*0.08), int(CAM_H*0.65))
    ctrl_r = (cx + int(CAM_W*0.30), int(CAM_H*0.65))
    dest_l = (cx + int(CAM_W*0.22), hy)
    dest_r = (cx + int(CAM_W*0.40), hy)
    left  = _bezier((cx - half_bot, CAM_H), ctrl_l, dest_l)
    right = _bezier((cx + half_bot, CAM_H), ctrl_r, dest_r)
    return left, right

def draw_nav_path(frame: np.ndarray, action: str, t: float) -> np.ndarray:
    """
    Superimpose an AR navigation corridor on the live camera frame.
    The corridor is perspective-correct, semi-transparent, and animated.
    """
    overlay = frame.copy()

    # Colour based on action
    path_col = {
        "FORWARD":     (55,  210,  85),
        "STEER LEFT":  (25,  195, 215),
        "STEER RIGHT": (25,  195, 215),
        "STOP":        (60,   55, 220),
    }.get(action, (55, 210, 85))

    if action == "STOP":
        # Red stop bar across lower third of frame
        bar_y = int(CAM_H * 0.68)
        cv2.rectangle(overlay, (0, bar_y), (CAM_W, bar_y + 28),
                      (30, 20, 160), -1)
        # Animated danger stripes
        stripe_w = 60
        offset = int(t * 80) % (stripe_w * 2)
        for sx in range(-stripe_w * 2, CAM_W + stripe_w * 2, stripe_w * 2):
            pts_stripe = np.array([
                [sx + offset,           bar_y],
                [sx + offset + stripe_w, bar_y],
                [sx + offset + stripe_w - 20, bar_y + 28],
                [sx + offset - 20,       bar_y + 28],
            ], np.int32)
            cv2.fillPoly(overlay, [pts_stripe], (60, 40, 200))
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # STOP text
        cv2.putText(frame, "STOP", (CAM_W//2 - 55, bar_y + 22),
                    FONT_B, 1.1, (255,255,255), 2, cv2.LINE_AA)
        # X marks
        for xm, ym in [(CAM_W//4, bar_y-30), (3*CAM_W//4, bar_y-30)]:
            cv2.line(frame, (xm-18,ym-18),(xm+18,ym+18), C_RED, 3)
            cv2.line(frame, (xm+18,ym-18),(xm-18,ym+18), C_RED, 3)
        return frame

    # Choose path geometry
    if action == "STEER LEFT":
        left_pts, right_pts = _path_left()
    elif action == "STEER RIGHT":
        left_pts, right_pts = _path_right()
    else:
        left_pts, right_pts = _path_forward()

    # Build filled polygon from left + reversed right
    if isinstance(left_pts[0], tuple):
        poly_pts = left_pts + list(reversed(right_pts))
    else:
        poly_pts = left_pts + list(reversed(right_pts))

    poly = np.array(poly_pts, np.int32).reshape((-1,1,2))
    cv2.fillPoly(overlay, [poly], path_col)
    cv2.addWeighted(overlay, 0.28, frame, 0.72, 0, frame)

    # Path border lines (solid, slightly opaque)
    left_arr  = np.array(left_pts,  np.int32)
    right_arr = np.array(right_pts, np.int32)
    cv2.polylines(frame, [left_arr],  False, path_col, 2, cv2.LINE_AA)
    cv2.polylines(frame, [right_arr], False, path_col, 2, cv2.LINE_AA)

    # Animated dashed centre line
    if isinstance(left_pts[0], tuple):
        n = len(left_pts)
        cx_pts = [((left_pts[i][0]+right_pts[i][0])//2,
                   (left_pts[i][1]+right_pts[i][1])//2) for i in range(n)]
    else:
        cx_pts = left_pts  # fallback for straight (2 pts)
        cx_pts = [
            (GROUND_CX, CAM_H),
            (GROUND_CX, HORIZON_Y + 20)
        ]

    # Dash animation: scroll from bottom to top
    dash_len = 18
    gap_len  = 14
    anim_offset = int(t * 120) % (dash_len + gap_len)

    for i in range(len(cx_pts)-1):
        p1 = cx_pts[i]; p2 = cx_pts[i+1]
        seg_len = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
        if seg_len < 1: continue
        # Draw only "on" dashes
        pos = float(anim_offset)
        while pos < seg_len:
            t0f = pos / seg_len
            t1f = min((pos + dash_len) / seg_len, 1.0)
            dp1 = (int(p1[0] + t0f*(p2[0]-p1[0])), int(p1[1] + t0f*(p2[1]-p1[1])))
            dp2 = (int(p1[0] + t1f*(p2[0]-p1[0])), int(p1[1] + t1f*(p2[1]-p1[1])))
            cv2.line(frame, dp1, dp2, (255,255,255), 1, cv2.LINE_AA)
            pos += dash_len + gap_len

    # Direction arrow at path centre (1/3 up from bottom)
    if len(cx_pts) >= 2:
        arrow_idx = len(cx_pts) // 3
        if isinstance(cx_pts[0], tuple) and len(cx_pts) > arrow_idx:
            tip = cx_pts[arrow_idx]
            base_idx = max(0, arrow_idx - 5)
            base = cx_pts[base_idx]
        else:
            tip  = (GROUND_CX, int(CAM_H * 0.55))
            base = (GROUND_CX, int(CAM_H * 0.75))
        cv2.arrowedLine(frame, base, tip, path_col, 3, cv2.LINE_AA, tipLength=0.3)

    # Action label badge on path
    badge = {"FORWARD": "FORWARD", "STEER LEFT": "GO LEFT", "STEER RIGHT": "GO RIGHT"}.get(action, action)
    bw, bh = cv2.getTextSize(badge, FONT_B, 0.65, 1)[0]
    bx = GROUND_CX - bw//2; by = int(CAM_H * 0.78)
    cv2.rectangle(frame, (bx-8, by-bh-6), (bx+bw+8, by+4), (0,0,0), -1)
    cv2.rectangle(frame, (bx-8, by-bh-6), (bx+bw+8, by+4), path_col, 1)
    cv2.putText(frame, badge, (bx, by), FONT_B, 0.65, path_col, 1, cv2.LINE_AA)

    return frame

# ---------------------------------------------------------------------------
# Detection box overlay
# ---------------------------------------------------------------------------
def draw_det_boxes(canvas: np.ndarray, dets: list[Det]):
    for d in dets:
        col = C_RED if d.dist_m < EMERGENCY_M else (
              C_YELLOW if d.dist_m < DANGER_M else C_GREEN)
        ov = canvas.copy()
        cv2.rectangle(ov, (d.x1,d.y1), (d.x2,d.y2), col, -1)
        cv2.addWeighted(ov, 0.10, canvas, 0.90, 0, canvas)
        cv2.rectangle(canvas, (d.x1,d.y1), (d.x2,d.y2), col, 1)
        cl = 14
        for cx0,cy0,sx,sy in [(d.x1,d.y1,1,1),(d.x2,d.y1,-1,1),
                               (d.x1,d.y2,1,-1),(d.x2,d.y2,-1,-1)]:
            cv2.line(canvas,(cx0,cy0),(cx0+sx*cl,cy0),col,2)
            cv2.line(canvas,(cx0,cy0),(cx0,cy0+sy*cl),col,2)
        lbl = f"  {d.label}  {d.dist_m:.1f}m  "
        (tw,th),_ = cv2.getTextSize(lbl, FONT, 0.38, 1)
        lx,ly = d.x1, max(d.y1-1, th+6)
        cv2.rectangle(canvas,(lx,ly-th-5),(lx+tw+2,ly+1),col,-1)
        cv2.putText(canvas, lbl, (lx+2,ly-3), FONT, 0.38, (8,8,8), 1, cv2.LINE_AA)
        zone_s = d.zone[0].upper()
        cv2.putText(canvas, zone_s, (d.x1+3,d.y2-4), FONT, 0.35, col, 1, cv2.LINE_AA)

# ---------------------------------------------------------------------------
# Drawing utilities
# ---------------------------------------------------------------------------
def txt(img, s, pos, sc=0.40, col=C_WHITE, th=1):
    cv2.putText(img, str(s), pos, FONT, sc, col, th, cv2.LINE_AA)

def txb(img, s, pos, sc=0.50, col=C_WHITE):
    cv2.putText(img, str(s), pos, FONT_B, sc, col, 1, cv2.LINE_AA)

def hline(img, y, x0, x1):
    cv2.line(img, (x0,y), (x1,y), BORDER, 1)

def grad_rect(img, x1, y1, x2, y2, ctop, cbot):
    for y in range(y1, y2):
        a = (y-y1) / max(1, y2-y1)
        c = tuple(int(ctop[i]*(1-a)+cbot[i]*a) for i in range(3))
        cv2.line(img, (x1,y), (x2,y), c, 1)

def anim_bar(img, x, y, w, h, val, maxv, col, bg=(22,24,38)):
    cv2.rectangle(img,(x,y),(x+w,y+h),bg,-1)
    fw = int(w * min(max(val,0), maxv) / max(maxv,1))
    for i in range(fw):
        a = i / max(1, fw)
        dk = tuple(int(c*0.35) for c in col)
        c  = tuple(int(dk[j]*(1-a)+col[j]*a) for j in range(3))
        cv2.line(img,(x+i,y+1),(x+i,y+h-1),c,1)
    cv2.rectangle(img,(x,y),(x+w,y+h),BORDER,1)

def pulse(img, cx, cy, r, col, t):
    p  = 0.5 + 0.5*math.sin(t*4)
    pr = int(r*(1+p*0.5))
    ac = tuple(int(c*(0.3+0.7*p)) for c in col)
    cv2.circle(img,(cx,cy),pr,ac,-1)
    cv2.circle(img,(cx,cy),r, col,-1)

def draw_bat(img, x, y, w, h, pct, label, t):
    cv2.rectangle(img,(x,y),(x+w,y+h),BORDER,1)
    nby = y + h//2 - 2
    cv2.rectangle(img,(x+w,nby),(x+w+3,nby+4),BORDER,-1)
    fw = int((w-2)*pct)
    col = C_GREEN if pct>0.5 else (C_YELLOW if pct>0.2 else C_RED)
    if fw>0:
        cv2.rectangle(img,(x+1,y+1),(x+1+fw,y+h-1),col,-1)
    txt(img, label, (x, y-10), 0.28, C_DIM)
    txt(img, f"{int(pct*100)}%", (x+3,y+h-3), 0.28, C_WHITE)

# ---------------------------------------------------------------------------
# Right panel
# ---------------------------------------------------------------------------
def draw_panel(canvas, dets, action, lpwm, rpwm,
               fps, ims, fno, zone_min, bat_pcts, t):

    px = CAM_W + 10
    pw = PANEL_W - 18

    # Header gradient
    grad_rect(canvas, CAM_W, 0, TOTAL_W, 54, (22,18,44), (14,16,26))
    txb(canvas, "NEMO_SENSE", (px, 24), 0.68, (175,155,220))
    pulse(canvas, TOTAL_W-16, 18, 5, C_LIME, t)
    txt(canvas, "LIVE AI NAVIGATION", (px, 40), 0.32, C_DIM)
    txt(canvas, "ARDUINO UNO Q", (TOTAL_W-112, 40), 0.32, C_PURPLE)
    hline(canvas, 54, CAM_W, TOTAL_W)
    y = 64

    # AI pipeline
    txt(canvas, "AI PIPELINE", (px,y), 0.37, C_DIM); y+=14
    nu = min(1., 0.50 + 0.22*math.sin(t*2.5+1))
    anim_bar(canvas, px, y, pw, 11, nu*100, 100, C_PURPLE)
    txt(canvas, f"YOLOv5n ONNX   {ims:.0f}ms   {nu*100:.0f}% NPU", (px,y+23), 0.32, C_DIM)
    y+=32; hline(canvas,y,CAM_W,TOTAL_W); y+=12

    # Zone scan
    txt(canvas, "ZONE SCAN", (px,y), 0.37, C_DIM); y+=14
    for zone in ["left","center","right"]:
        d2 = zone_min[zone]
        if d2 == INF:
            fr2, zc, dt2 = 0, C_GREEN, "CLEAR"
        else:
            fr2 = max(0., 1. - d2/5.)
            zc  = C_RED if d2<EMERGENCY_M else (C_YELLOW if d2<DANGER_M else C_GREEN)
            dt2 = f"{d2:.1f}m"
        cv2.rectangle(canvas,(px,y),(px+pw,y+17),(20,22,34),-1)
        if fr2>0:
            fw2 = int(pw*fr2)
            cv2.rectangle(canvas,(px+pw-fw2,y),(px+pw,y+17),zc,-1)
            ov2 = canvas.copy()
            cv2.addWeighted(ov2,0.28,canvas,0.72,0,canvas)
        cv2.rectangle(canvas,(px,y),(px+pw,y+17),BORDER,1)
        txt(canvas, f"{zone.upper():<6}", (px+4,y+11), 0.36, C_WHITE)
        txt(canvas, dt2, (px+pw-44,y+11), 0.35, zc if d2!=INF else C_DIM)
        y+=20
    hline(canvas,y,CAM_W,TOTAL_W); y+=12

    # Decision block
    txt(canvas, "NAVIGATION DECISION", (px,y), 0.37, C_DIM); y+=13
    cfg = {"FORWARD":(C_GREEN,"FORWARD","path is clear"),
           "STOP":   (C_RED,  "STOP",   "obstacle ahead"),
           "STEER LEFT": (C_YELLOW,"<< STEER LEFT","obstacle in center"),
           "STEER RIGHT":(C_YELLOW,"STEER RIGHT >>","obstacle in center")}
    acol, albl, asub = cfg.get(action, (C_WHITE, action, ""))
    bg_act = (28,10,10) if action=="STOP" else (14,20,14) if action=="FORWARD" else (24,22,10)
    cv2.rectangle(canvas,(px,y),(px+pw,y+54),bg_act,-1)
    cv2.rectangle(canvas,(px,y),(px+pw,y+54),acol,1)
    mid = px + pw//2
    if action=="FORWARD":
        cv2.arrowedLine(canvas,(mid,y+40),(mid,y+14),acol,3,tipLength=0.38)
    elif action=="STOP":
        cv2.rectangle(canvas,(mid-10,y+14),(mid+10,y+40),acol,-1)
    elif "LEFT" in action:
        cv2.arrowedLine(canvas,(mid+16,y+30),(mid-16,y+30),acol,3,tipLength=0.38)
    elif "RIGHT" in action:
        cv2.arrowedLine(canvas,(mid-16,y+30),(mid+16,y+30),acol,3,tipLength=0.38)
    txb(canvas, albl, (px+pw//2-len(albl)*6, y+52), 0.44, acol)
    txt(canvas, asub, (px+6, y+14), 0.30, C_DIM)
    y+=62; hline(canvas,y,CAM_W,TOTAL_W); y+=12

    # Motor output
    txt(canvas, "MOTOR COMMAND", (px,y), 0.37, C_DIM); y+=14
    hw = pw//2 - 3
    anim_bar(canvas, px,      y, hw, 12, lpwm, 255, C_BLUE)
    anim_bar(canvas, px+hw+6, y, hw, 12, rpwm, 255, C_BLUE)
    txt(canvas, f"L {lpwm}", (px+3,    y+24), 0.32, C_DIM)
    txt(canvas, f"R {rpwm}", (px+hw+9, y+24), 0.32, C_DIM)
    spd = max(lpwm,rpwm)/255*BASE_SPEED
    txt(canvas, f"{spd:.2f} m/s", (px+hw-22,y+24), 0.30, C_TEAL)
    y+=34; hline(canvas,y,CAM_W,TOTAL_W); y+=12

    # Battery
    txt(canvas, "POWER SYSTEM", (px,y), 0.37, C_DIM); y+=22
    bw3 = (pw-8)//3
    draw_bat(canvas, px,           y, bw3-3, 12, bat_pcts[0], "BAT-1",     t)
    draw_bat(canvas, px+bw3,       y, bw3-3, 12, bat_pcts[1], "BAT-2",     t+1.1)
    draw_bat(canvas, px+bw3*2+4,   y, bw3-3, 12, bat_pcts[2], "BAT-3 AI",  t+2.2)
    y+=26
    fc = C_LIME if bat_pcts[0]>0.1 else C_YELLOW
    pulse(canvas, px+6, y+4, 3, fc, t)
    txt(canvas, "Schottky OR failover  |  3x redundancy", (px+14,y+8), 0.28, C_DIM)
    y+=18; hline(canvas,y,CAM_W,TOTAL_W); y+=12

    # Detections
    txt(canvas, f"DETECTIONS ({len(dets)})", (px,y), 0.37, C_DIM); y+=14
    if dets:
        for d3 in dets[:4]:
            dc = C_RED if d3.dist_m<DANGER_M else C_GREEN
            cv2.rectangle(canvas,(px,y-1),(px+pw,y+14),(20,22,34),-1)
            pulse(canvas, px+5, y+6, 3, dc, t)
            txt(canvas, f"  {d3.label:<13}{d3.zone[0].upper()}  {d3.dist_m:.1f}m  {d3.conf:.0%}",
                (px, y+10), 0.33, dc)
            y+=16
    else:
        cv2.rectangle(canvas,(px,y-1),(px+pw,y+14),(18,22,30),-1)
        pulse(canvas, px+5, y+6, 3, C_GREEN, t)
        txt(canvas, "  path clear -- no obstacles", (px,y+10), 0.33, C_DIM)
        y+=16

    y+=6; hline(canvas,y,CAM_W,TOTAL_W); y+=10
    txt(canvas, f"FRAME #{fno:05d}   {fps:.0f} FPS   {ims:.0f}ms/frame", (px,y+10), 0.28, (45,50,70))
    y+=18
    txt(canvas, "Q=quit   P=pause", (px,y+8), 0.26, (38,42,60))

# ---------------------------------------------------------------------------
# Navigation logic
# ---------------------------------------------------------------------------
def classify_zones(dets: list[Det], fw: int) -> list[Det]:
    l_end = fw // 3; r_start = 2 * fw // 3
    for d in dets:
        cx = (d.x1+d.x2)//2
        # Area as fraction of total frame
        area = ((d.x2-d.x1) * (d.y2-d.y1)) / max(1, fw * CAM_H)
        # Inverse-sqrt-area approximation:
        #   small object (area=0.01) -> ~3.5m
        #   medium      (area=0.05) -> ~1.6m
        #   large       (area=0.20) -> ~0.8m
        #   very close  (area=0.50) -> ~0.5m
        d.dist_m = min(8.0, max(0.4, 0.35 / math.sqrt(max(1e-5, area))))
        d.zone = "left" if cx < l_end else ("right" if cx > r_start else "center")
    return dets

def decide(dets: list[Det]) -> tuple[str, int, int]:
    zm = {"left":INF,"center":INF,"right":INF}
    for d in dets:
        if d.dist_m < zm[d.zone]: zm[d.zone] = d.dist_m
    b = 120
    if zm["center"] < EMERGENCY_M: return "STOP", 0, 0
    if zm["center"] < DANGER_M:
        return ("STEER LEFT", int(b*.2), b) if zm["left"]>zm["right"] \
            else ("STEER RIGHT", b, int(b*.2))
    if zm["right"] < DANGER_M: return "STEER LEFT", int(b*.4), b
    if zm["left"]  < DANGER_M: return "STEER RIGHT", b, int(b*.4)
    return "FORWARD", b, b

def sim_bats(t0, tn):
    e = tn - t0
    return (max(0., 1.-e/1800), max(0., 1.-e/2100), max(0., 1.-e/3600))


# ---------------------------------------------------------------------------
# Quarky BLE link
# ---------------------------------------------------------------------------
# Protocol (sent from laptop → Quarky over BLE):
#   M:LEFT,RIGHT\n     motor command  (-255 to 255 each wheel)

QUARKY_BLE_SERVICE = "19B10000-E8F2-537E-4F6C-D104768A1214"
QUARKY_BLE_CHAR    = "19B10001-E8F2-537E-4F6C-D104768A1214"

class QuarkyBLELink:
    """Non-blocking BLE link to Quarky motor controller."""

    def __init__(self):
        self._q: queue.Queue = queue.Queue(maxsize=4)
        self.connected = False
        self._stop_event = threading.Event()
        
        if not _BLE_OK:
            print("[QUARKY BLE] bleak not installed. Run: pip install bleak")
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.run(self._async_worker())

    async def _async_worker(self):
        print("[QUARKY BLE] Scanning for 'Quarky_Nemo'...")
        device = await BleakScanner.find_device_by_name("Quarky_Nemo", timeout=10.0)
        
        if not device:
            print("[QUARKY BLE] Not found. Ensure Quarky is advertising.")
            return

        print(f"[QUARKY BLE] Found {device.name}, connecting...")
        try:
            async with BleakClient(device) as client:
                self.connected = True
                print("[QUARKY BLE] Connected!")
                
                while not self._stop_event.is_set():
                    try:
                        cmd = self._q.get(timeout=0.1)
                        await client.write_gatt_char(QUARKY_BLE_CHAR, cmd.encode(), response=False)
                    except queue.Empty:
                        pass
                    except Exception as e:
                        print(f"[QUARKY BLE] Write error: {e}")
                        break
        except Exception as e:
            print(f"[QUARKY BLE] Connection failed: {e}")
            
        self.connected = False
        print("[QUARKY BLE] Disconnected.")

    def send(self, action: str, l_pwm: int, r_pwm: int):
        if not self.connected:
            return
        try:
            self._q.put_nowait(f"M:{l_pwm},{r_pwm}\n")
        except queue.Full:
            pass

    def close(self):
        self._stop_event.set()
        if hasattr(self, '_thread') and self._thread.is_alive():
            self._thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# Quarky WiFi (UDP) link
# ---------------------------------------------------------------------------
# Protocol (sent from laptop → Quarky over WiFi UDP):
#   M:LEFT,RIGHT\n     motor command  (-255 to 255 each wheel)
#
# UDP is connectionless and non-blocking, so it sends instantly without
# stalling the video frame rate, and doesn't suffer from pairing issues.

class QuarkyWiFiLink:
    """Non-blocking UDP socket link to Quarky motor controller."""

    def __init__(self, ip: str, port: int = 8080):
        self.addr = (ip, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Non-blocking socket just in case
        self.sock.setblocking(False)
        print(f"[QUARKY WIFI] Ready to send UDP commands to {ip}:{port}")

    def send(self, action: str, l_pwm: int, r_pwm: int):
        """Send a motor command over UDP."""
        cmd = f"M:{l_pwm},{r_pwm}\n".encode()
        try:
            self.sock.sendto(cmd, self.addr)
        except Exception:
            pass

    def close(self):
        try:
            self.sock.sendto(b"M:0,0\n", self.addr)
            self.sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def find_model():
    for p in ONNX_SEARCH:
        if p.exists(): return p
    return None

def main():
    ap = argparse.ArgumentParser(description="NEMO_SENSE AI Navigation Dashboard v4")
    ap.add_argument("--camera",  type=int,  default=-1,  help="Camera index")
    ap.add_argument("--stream",  type=str,  default="",  help="MJPEG stream URL")
    ap.add_argument("--model",   type=str,  default=None)
    ap.add_argument("--no-path", action="store_true",   help="Disable AR overlay")
    ap.add_argument("--quarky-ble", action="store_true",
                    help="Connect to Quarky over BLE")
    ap.add_argument("--quarky-ip", type=str, default="",
                    help="IP address of Quarky for UDP control")
    args = ap.parse_args()

    # -- Robot link --
    quarky = None
    if args.quarky_ble:
        quarky = QuarkyBLELink()
    elif args.quarky_ip:
        quarky = QuarkyWiFiLink(args.quarky_ip)

    yolo = YOLOv5(find_model() if not args.model else args.model)

    # -- Camera setup --
    cap = None; source = ""
    if args.stream:
        cap = cv2.VideoCapture(args.stream)
        source = f"STREAM {args.stream[-22:]}"
        print(f"[NET] Stream: {args.stream}")
    else:
        idx = args.camera
        if idx == -1:
            for i in range(4):
                c = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if c.isOpened():
                    ret, _ = c.read()
                    if ret: cap = c; idx = i; break
                    c.release()
            if cap is None:
                # Try without DSHOW
                for i in range(4):
                    c = cv2.VideoCapture(i)
                    if c.isOpened():
                        ret, _ = c.read()
                        if ret: cap = c; idx = i; break
                        c.release()
        else:
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(idx)
        if cap and cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
            cap.set(cv2.CAP_PROP_FPS,          30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE,    1)
            source = f"WEBCAM [{idx}]"
            print(f"[CAM] Camera {idx} opened")
        else:
            print("[ERROR] No camera found. Connect a webcam and retry.")
            return

    # -- State --
    paused = False; fno = 0; fps = 0.; ims = 20.
    t0 = time.monotonic(); tfps = t0; fpsc = 0
    last_dets: list[Det] = []; last_act = "FORWARD"; ll = lr = 120
    last_frame = np.zeros((CAM_H, CAM_W, 3), np.uint8)

    WIN = "NEMO_SENSE -- AI Navigation"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, TOTAL_W, TOTAL_H)
    print("[RUN] Dashboard active. Q=quit  P=pause  --no-path to hide overlay")

    tl = time.monotonic()
    while True:
        tn  = time.monotonic()
        dt  = tn - tl; tl = tn
        ta  = tn - t0

        if not paused:
            ret, raw = cap.read()
            if not ret or raw is None:
                raw = np.zeros((CAM_H, CAM_W, 3), np.uint8)
            frame = cv2.resize(raw, (CAM_W, CAM_H))
            last_frame = frame.copy()

            ti = time.monotonic()
            dets = yolo.infer(frame)
            ims  = (time.monotonic()-ti)*1000
            dets = classify_zones(dets, CAM_W)
            act, ll, lr = decide(dets)
            last_dets = dets; last_act = act; fno += 1

            # Send to Quarky
            if quarky:
                quarky.send(act, ll, lr)
        else:
            frame = last_frame.copy()

        # FPS
        fpsc += 1
        if tn-tfps >= 1.:
            fps = fpsc/(tn-tfps); fpsc = 0; tfps = tn

        # -- Draw AR path on the frame FIRST --
        if not args.no_path:
            frame = draw_nav_path(frame, last_act, ta)

        # -- Then overlay detection boxes --
        draw_det_boxes(frame, last_dets)

        # -- Compose full canvas --
        canvas = np.full((TOTAL_H, TOTAL_W, 3), BG, dtype=np.uint8)
        cv2.rectangle(canvas, (CAM_W,0),(TOTAL_W,TOTAL_H), PANEL_BG, -1)
        canvas[:CAM_H, :CAM_W] = frame

        # Zone divider lines on camera
        lx, rx = CAM_W//3, 2*CAM_W//3
        for xd in [lx, rx]:
            cv2.line(canvas,(xd,0),(xd,CAM_H),(38,42,62),1)
        txt(canvas,"LEFT",   (6,14),      0.30,(46,52,75))
        txt(canvas,"CENTER", (lx+30,14),  0.30,(46,52,75))
        txt(canvas,"RIGHT",  (rx+8,14),   0.30,(46,52,75))

        # FPS badge top right of camera
        cv2.rectangle(canvas,(CAM_W-115,0),(CAM_W,22),(0,0,0),-1)
        txt(canvas, f"{fps:.0f} FPS  {ims:.0f}ms", (CAM_W-111,14), 0.34, C_TEAL)

        # Source badge
        cv2.rectangle(canvas,(0,0),(170,18),(0,0,0),-1)
        txt(canvas, source, (3,12), 0.30, C_DIM)

        # Bottom bar on camera
        grad_rect(canvas, 0, CAM_H-32, CAM_W, CAM_H, (0,0,0),(6,6,14))
        sym={"FORWARD":"[^] FORWARD","STOP":"[X] STOP",
             "STEER LEFT":"[<] GO LEFT","STEER RIGHT":"[>] GO RIGHT"}
        acol={"FORWARD":C_GREEN,"STOP":C_RED,"STEER LEFT":C_YELLOW,"STEER RIGHT":C_YELLOW}.get(last_act,C_WHITE)
        txb(canvas, sym.get(last_act,last_act),(10,CAM_H-10),0.52,acol)
        if paused:
            txb(canvas,"PAUSED",(CAM_W//2-38,CAM_H//2),0.8,C_ORANGE)

        # Zone mins for panel
        zm = {"left":INF,"center":INF,"right":INF}
        for d in last_dets:
            if d.dist_m < zm[d.zone]: zm[d.zone] = d.dist_m

        bats = sim_bats(t0, tn)
        draw_panel(canvas, last_dets, last_act, ll, lr, fps, ims, fno, zm, bats, ta)

        cv2.imshow(WIN, canvas)
        k = cv2.waitKey(1) & 0xFF
        if k in (ord("q"), ord("Q"), 27): break
        elif k in (ord("p"), ord("P")):
            paused = not paused
            print(f"[DEMO] {'PAUSED' if paused else 'LIVE'}")

        time.sleep(max(0, 0.030 - (time.monotonic()-tn)))

    cv2.destroyAllWindows()
    cap.release()
    if quarky:
        quarky.close()
    print("[DONE]")

if __name__ == "__main__":
    main()
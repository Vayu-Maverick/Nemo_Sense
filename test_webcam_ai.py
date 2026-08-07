# -*- coding: utf-8 -*-
"""
test_webcam_ai.py — Netra Webcam + AI Smoke Test

Tests:
  1. USB webcam detection (scans indexes 0-10, all backends incl. USB hub cameras)
  2. YOLOv5n ONNX model inference on a real frame
  3. Prints detected objects with confidence scores

Usage:
    python test_webcam_ai.py              # test with real webcam
    python test_webcam_ai.py --sim        # test with simulated frames
    python test_webcam_ai.py --show       # open a live OpenCV preview window
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import cv2
import numpy as np

# Fix Windows console encoding
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ── Path setup ────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON_DIR = os.path.join(HERE, "python")
sys.path.insert(0, PYTHON_DIR)

PY_EXEC = sys.executable
YOLO_PATH = os.path.join(HERE, "yolov5n.onnx")

OBSTACLE_CLASSES = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle",
    5: "bus", 7: "truck", 9: "traffic light", 10: "fire hydrant",
    11: "stop sign", 13: "bench", 14: "bird", 15: "cat", 16: "dog",
    24: "backpack", 25: "umbrella", 28: "suitcase", 56: "chair",
    57: "couch", 58: "potted plant",
}
ALL_CLASSES = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck","boat",
    "traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat",
    "dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack",
    "umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball",
    "kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket",
    "bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple",
    "sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair",
    "couch","potted plant","bed","dining table","toilet","tv","laptop","mouse",
    "remote","keyboard","cell phone","microwave","oven","toaster","sink",
    "refrigerator","book","clock","vase","scissors","teddy bear","hair drier",
    "toothbrush",
]

def scan_webcam(max_index: int = 10) -> tuple:
    """Scan for USB webcam across all backends. Returns (cap, index, backend_name)."""
    import platform
    print(f"\n{'='*60}")
    print(f"  NETRA -- USB Webcam + AI Smoke Test")
    print(f"{'='*60}")
    print(f"\n[SCAN] Scanning for USB webcam (indexes 0-{max_index})...")

    backends = []
    if platform.system() == "Windows":
        backends = [
            (cv2.CAP_DSHOW, "DirectShow (best for USB hub on Windows)"),
            (cv2.CAP_MSMF,  "Media Foundation"),
            (cv2.CAP_ANY,   "Auto-detect"),
        ]
    else:
        backends = [
            (cv2.CAP_V4L2, "V4L2 (Linux)"),
            (cv2.CAP_ANY,  "Auto-detect"),
        ]

    for backend_id, backend_name in backends:
        for idx in range(max_index + 1):
            try:
                cap = cv2.VideoCapture(idx, backend_id)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.size > 0:
                        print(f"  [FOUND] Camera index={idx}  backend={backend_name}")
                        print(f"          Frame size: {frame.shape[1]}x{frame.shape[0]}")
                        # Warm up
                        for _ in range(5):
                            cap.read()
                        return cap, idx, backend_name
                    cap.release()
            except Exception:
                pass

    print("  [MISS] No USB webcam found.")
    print("         -> Plug your webcam into the USB hub, then into the rover/PC.")
    print("         -> On Windows: check Device Manager -> Imaging Devices.")
    return None, -1, "none"

def run_yolo(net, frame: np.ndarray, conf_thresh: float = 0.45):
    """Run YOLOv5n via cv2.dnn and return list of (label, confidence)."""
    blob = cv2.dnn.blobFromImage(
        frame, 1 / 255.0, (640, 640), swapRB=True, crop=False
    )
    net.setInput(blob)
    preds = net.forward()
    preds = np.squeeze(preds[0]) if preds.ndim == 4 else np.squeeze(preds)

    found = []
    for row in preds:
        conf = float(row[4])
        if conf > conf_thresh:
            class_id = int(np.argmax(row[5:]))
            class_conf = float(row[5 + class_id]) * conf
            if class_conf > conf_thresh:
                label = ALL_CLASSES[class_id] if class_id < len(ALL_CLASSES) else f"cls_{class_id}"
                found.append((label, class_conf, class_id))
    return found

def simulated_frame(t: float, w: int = 640, h: int = 480) -> np.ndarray:
    """Generate a synthetic frame for testing."""
    import math
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[h // 2:, :] = [80, 80, 80]   # floor
    frame[:h // 2, :] = [120, 90, 60]  # sky/wall
    # Moving red blob
    cx = int(w // 2 + 100 * math.sin(t * 0.3))
    cy = h // 2 + 20
    cv2.rectangle(frame, (cx - 30, cy - 60), (cx + 30, cy + 60), (50, 50, 200), -1)
    cv2.putText(frame, "SIMULATED FRAME", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    return frame

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim",   action="store_true", help="Use simulated frames")
    parser.add_argument("--show",  action="store_true", help="Show live preview window")
    parser.add_argument("--frames", type=int, default=5, help="Number of test frames")
    parser.add_argument("--conf",   type=float, default=0.45, help="YOLO confidence threshold")
    args = parser.parse_args()

    # ── Load YOLO model ───────────────────────────────────────────────────
    print(f"\n[MODEL] Loading YOLOv5n model from: {YOLO_PATH}")
    if not os.path.exists(YOLO_PATH):
        print(f"  [ERROR] Model file not found: {YOLO_PATH}")
        sys.exit(1)
    net = cv2.dnn.readNetFromONNX(YOLO_PATH)
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    print("  [OK] Model loaded successfully!")

    # ── Camera ────────────────────────────────────────────────────────────
    cap = None
    if not args.sim:
        cap, idx, bname = scan_webcam()
        if cap is None:
            print("\n[WARN] Falling back to SIMULATED frames for AI test.")
            args.sim = True

    # ── Test frames ───────────────────────────────────────────────────────
    print(f"\n[RUN] Running AI inference on {args.frames} test frame(s)...")
    print(f"   Confidence threshold: {args.conf}")
    print()

    for i in range(args.frames):
        t0 = time.time()
        if args.sim:
            frame = simulated_frame(float(i))
        else:
            ret, frame = cap.read()
            if not ret:
                print(f"  Frame {i+1}: ❌ read failed")
                continue

        detections = run_yolo(net, frame, args.conf)
        elapsed_ms = (time.time() - t0) * 1000

        print(f"  Frame {i+1}/{args.frames}  ({elapsed_ms:.0f}ms)")
        if detections:
            for label, conf, cls_id in detections:
                is_obstacle = cls_id in OBSTACLE_CLASSES
                tag = "[OBSTACLE]" if is_obstacle else "[object]  "
                print(f"    {tag}  {label:20s}  {conf*100:.1f}%")
        else:
            print("    (no detections above threshold)")

        if args.show:
            # Draw boxes
            display = frame.copy()
            for label, conf, cls_id in detections:
                cv2.putText(display, f"{label} {conf:.2f}",
                            (10, 30 + detections.index((label, conf, cls_id)) * 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (0, 255, 0) if cls_id not in OBSTACLE_CLASSES else (0, 0, 255), 2)
            cv2.imshow("Netra — Test Frame", display)
            if cv2.waitKey(500) & 0xFF == ord("q"):
                break

    if cap:
        cap.release()
    if args.show:
        cv2.destroyAllWindows()

    print(f"\n{'='*60}")
    print("  [PASS] Test complete!")
    print(f"{'='*60}")
    print("\nNext steps:")
    print("  1. Run the full simulator:  python rover_simulator.py --no-ble")
    print("  2. Plug USB webcam into hub → hub into rover → rerun")
    print("  3. Enable BLE for phone camera:  python rover_simulator.py")
    print()

if __name__ == "__main__":
    main()

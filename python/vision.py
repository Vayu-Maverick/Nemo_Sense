"""
vision.py — Computer-vision pipeline for the Netra Blind Guide Rover.

Runs YOLOv5n (object detection) on every camera frame, fuses them into a
per-zone obstacle map, and produces an actionable VisionResult.

Camera priority:
  1. Frame injected externally (from BLE phone stream)
  2. USB webcam via USB hub (auto-scans indexes 0-10, all backends)
  3. Simulated test frame (moving sine-wave pattern) if no webcam found

Designed for ~5-10 FPS on a PC or the UNO Q's Cortex-A53 at 320×320 input.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None  # handled at init time

from config import (
    CAMERA_INDEX,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    CAMERA_FPS,
    YOLO_MODEL_PATH,
    YOLO_INPUT_SIZE,
    YOLO_CONF_THRESHOLD,
    YOLO_IOU_THRESHOLD,
    DEPTH_DANGER_THRESHOLD,
    DEPTH_EMERGENCY_THRESHOLD,
    ZONE_LEFT_END,
    ZONE_CENTER_END,
    OBSTACLE_CLASS_IDS,
    ONNX_THREADS,
)

logger = logging.getLogger(__name__)

# ── Data classes ──────────────────────────────────────────────────────────

@dataclass
class ObstacleInfo:
    """Single detected obstacle with estimated distance and zone."""
    label: str
    confidence: float
    distance_m: float              # estimated distance in metres
    zone: str                      # "left", "center", or "right"
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2) in input coords

@dataclass
class VisionResult:
    """Aggregated result of one vision cycle."""
    obstacles: list[ObstacleInfo] = field(default_factory=list)
    closest_distance: float = float("inf")
    recommended_action: str = "clear"   # clear | steer_left | steer_right | stop
    zone_min_dist: dict = field(default_factory=lambda: {
        "left": float("inf"),
        "center": float("inf"),
        "right": float("inf"),
    })
    frame_time_ms: float = 0.0
    source: str = "unknown"             # "webcam" | "ble_phone" | "simulated"

# ── Helper: non-maximum suppression ──────────────────────────────────────

def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> list[int]:
    """
    Greedy NMS.  boxes shape (N, 4) as x1,y1,x2,y2;  scores shape (N,).
    Returns list of kept indices.
    """
    if len(boxes) == 0:
        return []

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []

    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        remaining = np.where(iou <= iou_thresh)[0]
        order = order[remaining + 1]

    return keep

# ── Simulated camera ──────────────────────────────────────────────────────

class SimulatedCamera:
    """
    Generates synthetic BGR frames for testing when no USB webcam is present.
    Simulates a forward-facing hallway with a moving person obstacle using an AI-generated sprite.
    """

    def __init__(self, width: int = 640, height: int = 480, fps: int = 15):
        self.width = width
        self.height = height
        self.fps = fps
        self._frame_count = 0
        self._person_img = None
        self._person_mask = None

        # Vehicle-centered state
        self.person_x = float(width // 2)
        self.person_dir = 2.0  # wander speed

        logger.warning(
            "No webcam found — using SIMULATED camera. "
            "Plug your webcam directly in and restart to use real camera."
        )

        # Load the AI-generated person sprite if available
        import glob
        import os
        img_pattern = r"C:\Users\Admin\.gemini\antigravity\brain\*\sim_person_*.png"
        matches = glob.glob(img_pattern)
        if matches:
            try:
                img = cv2.imread(matches[-1])
                # Resize to something reasonable for a 640x480 frame
                h, w = img.shape[:2]
                scale = 200 / h
                new_w, new_h = int(w * scale), 200
                img = cv2.resize(img, (new_w, new_h))
                # Create a mask to remove the white background
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
                self._person_img = img
                self._person_mask = mask
                logger.info("Loaded simulated person sprite from %s", matches[-1])
            except Exception as e:
                logger.warning("Failed to load simulated person sprite: %s", e)

    def update_physics(self, l_pwm: int, r_pwm: int):
        """Called by simulator to apply vehicle turning."""
        # If rover steers left (R > L), scene shifts right (+X)
        # If rover steers right (L > R), scene shifts left (-X)
        turn_rate = (r_pwm - l_pwm) * 0.1
        self.person_x += turn_rate

    def read(self) -> tuple[bool, np.ndarray]:
        """Generate the next synthetic frame."""
        self._frame_count += 1
        t = self._frame_count / max(self.fps, 1)

        # Wander the person slowly
        self.person_x += self.person_dir
        if self.person_x > self.width + 100:
            self.person_x = -50
            self.person_dir = 2.0
        elif self.person_x < -100:
            self.person_x = self.width + 50
            self.person_dir = -2.0

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # ── Floor (grey gradient) ─────────────────────────────────────────
        for y in range(self.height // 2, self.height):
            brightness = int(60 + 80 * (y - self.height // 2) / (self.height // 2))
            frame[y, :] = [brightness, brightness, brightness]

        # ── Walls (side stripes) ──────────────────────────────────────────
        frame[:, :30] = [40, 40, 60]
        frame[:, -30:] = [40, 40, 60]

        # ── Sky / ceiling (blue-grey) ─────────────────────────────────────
        frame[: self.height // 2, :] = [90, 70, 50]

        # ── Horizon line ─────────────────────────────────────────────────
        frame[self.height // 2 - 2 : self.height // 2 + 2, :] = [120, 120, 120]

        # ── Moving obstacle ───────────────────────────────────────────────
        cx = int(self.person_x)
        cy = self.height // 2 + 30

        if self._person_img is not None:
            # Overlay the realistic person sprite
            ph, pw = self._person_img.shape[:2]
            x1 = cx - pw // 2
            y1 = cy - ph // 2
            x2 = x1 + pw
            y2 = y1 + ph

            # Clip to frame boundaries
            x1_c, y1_c = max(0, x1), max(0, y1)
            x2_c, y2_c = min(self.width, x2), min(self.height, y2)
            
            if x1_c < x2_c and y1_c < y2_c:
                # Calculate slice indices for the sprite
                sx1 = x1_c - x1
                sy1 = y1_c - y1
                sx2 = sx1 + (x2_c - x1_c)
                sy2 = sy1 + (y2_c - y1_c)

                roi = frame[y1_c:y2_c, x1_c:x2_c]
                sprite = self._person_img[sy1:sy2, sx1:sx2]
                mask = self._person_mask[sy1:sy2, sx1:sx2]
                mask_inv = cv2.bitwise_not(mask)

                # Composite
                bg = cv2.bitwise_and(roi, roi, mask=mask_inv)
                fg = cv2.bitwise_and(sprite, sprite, mask=mask)
                frame[y1_c:y2_c, x1_c:x2_c] = cv2.add(bg, fg)
        else:
            # Fallback red rectangle
            bw, bh = 80, 140
            x1, y1 = cx - bw // 2, cy - bh // 2
            x2, y2 = cx + bw // 2, cy + bh // 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 40, 200), -1)

        # ── Distance indicator text ───────────────────────────────────────
        dist_text = f"SIM t={t:.1f}s"
        cv2.putText(frame, dist_text, (5, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 255, 200), 1)

        return True, frame

    def isOpened(self) -> bool:
        return True

    def release(self):
        pass

    def set(self, *args):
        pass

# ── Direct Webcam Opener ──────────────────────────────────────────────────

def _scan_for_webcam(max_index: int = 0) -> cv2.VideoCapture | None:
    """
    Open the directly-connected webcam.
    Tries index 0 to avoid driver hangs on virtual cameras.
    Returns an open VideoCapture or None.
    """
    import platform
    backend = cv2.CAP_MSMF if platform.system() == "Windows" else cv2.CAP_ANY

    logger.info("Opening webcam (direct connection) via MSMF...")
    for idx in range(max_index + 1):
        try:
            cap = cv2.VideoCapture(idx, backend)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    logger.info("Webcam opened: index=%d  res=%dx%d", idx, actual_w, actual_h)
                    return cap
                cap.release()
        except Exception as exc:
            logger.debug("Camera index=%d failed: %s", idx, exc)

    return None

# ── Simple depth estimator (no MiDaS ONNX needed) ────────────────────────

def _estimate_depth_from_bbox(bbox: tuple[int, int, int, int],
                               frame_h: int, frame_w: int) -> float:
    """
    Heuristic depth from bounding-box bottom-edge position and size.

    Objects at the bottom of frame / large bounding boxes are closer.
    Returns an approximate distance in metres.
    """
    x1, y1, x2, y2 = bbox
    box_h = y2 - y1
    box_w = x2 - x1
    box_area_frac = (box_h * box_w) / max(frame_h * frame_w, 1)
    bottom_frac = y2 / max(frame_h, 1)  # 0=top 1=bottom

    # Larger area + lower on frame → closer
    # Tuned: area=0.5 → ~0.5 m,  area=0.01 → ~3.0 m
    area_dist = 0.4 / (box_area_frac + 0.03)
    bottom_dist = 4.0 * (1.0 - bottom_frac) + 0.3

    dist = 0.6 * area_dist + 0.4 * bottom_dist
    return float(np.clip(dist, 0.2, 10.0))

# ── Main class ────────────────────────────────────────────────────────────

class VisionSystem:
    """
    Initialise vision system.  Call process_frame(frame=None) per cycle.

    Camera priority:
      1. BLE phone frame (injected via latest_ble_frame)
      2. Real USB webcam (auto-detected including USB hub cameras)
      3. Simulated camera (for testing with no hardware)
    """

    def __init__(self, yolo_path: str = YOLO_MODEL_PATH):
        self.latest_ble_frame: np.ndarray | None = None

        # ── Load YOLOv5n ONNX model ───────────────────────────────────────
        if ort is not None:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = ONNX_THREADS
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            try:
                logger.info("Loading YOLOv5n from %s", yolo_path)
                self._yolo = ort.InferenceSession(yolo_path, sess_options=opts)
                self._yolo_input_name = self._yolo.get_inputs()[0].name
                # Detect expected dtype (float32 or float16)
                self._yolo_dtype = self._yolo.get_inputs()[0].type
                # Detect expected input size from model shape
                model_shape = self._yolo.get_inputs()[0].shape
                self._yolo_input_size = int(model_shape[2]) if len(model_shape) >= 3 else YOLO_INPUT_SIZE
                self._use_onnx = True
                logger.info("YOLOv5n loaded via ONNX Runtime (dtype=%s size=%dx%d)",
                            self._yolo_dtype, self._yolo_input_size, self._yolo_input_size)
            except Exception as exc:
                logger.warning("ONNX Runtime load failed (%s), using cv2.dnn fallback", exc)
                self._use_onnx = False
                self._load_cv2_dnn(yolo_path)
        else:
            logger.info("onnxruntime not installed — using cv2.dnn fallback")
            self._use_onnx = False
            self._load_cv2_dnn(yolo_path)

        # ── Camera ────────────────────────────────────────────────────────
        self._cap = None
        self._simulated = False
        self._open_camera()

        logger.info("VisionSystem ready (simulated=%s, onnx=%s)",
                    self._simulated, self._use_onnx)

    # ── cv2.dnn fallback ──────────────────────────────────────────────────

    def _load_cv2_dnn(self, yolo_path: str):
        try:
            self._dnn_net = cv2.dnn.readNetFromONNX(yolo_path)
            self._dnn_net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self._dnn_net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self._use_cv2dnn = True
            logger.info("YOLOv5n loaded via cv2.dnn")
        except Exception as exc:
            logger.error("cv2.dnn load failed too: %s — running detection-free", exc)
            self._use_cv2dnn = False

    # ── Camera management ─────────────────────────────────────────────────

    def _open_camera(self):
        """Try USB webcam (incl. USB hub), fall back to simulator."""
        cap = _scan_for_webcam(max_index=0)
        if cap is not None:
            self._cap = cap
            self._simulated = False
        else:
            self._cap = SimulatedCamera(CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS)
            self._simulated = True

    def capture_frame(self) -> tuple[np.ndarray | None, str]:
        """
        Return (frame, source) where source is 'ble_phone', 'webcam', or 'simulated'.
        BLE phone frame takes priority over local camera.
        """
        # Priority 1: BLE phone frame
        if self.latest_ble_frame is not None:
            frame = self.latest_ble_frame.copy()
            self.latest_ble_frame = None  # consume
            return frame, "ble_phone"

        # Priority 2: USB webcam / simulated camera
        if self._cap is None:
            self._open_camera()
        if self._cap is None:
            return None, "none"

        ret, frame = self._cap.read()
        if not ret or frame is None:
            logger.warning("Frame read failed — retrying camera open")
            if not self._simulated:
                self._cap.release()
                self._cap = None
                self._open_camera()
            return None, "none"

        source = "simulated" if self._simulated else "webcam"
        return frame, source

    # ── YOLO inference ────────────────────────────────────────────────────

    def _run_yolo(self, frame: np.ndarray):
        """Run YOLOv5n inference. Returns raw output tensor."""
        # Use model's actual input size (640 for standard YOLOv5, 320 for nano)
        input_size = getattr(self, "_yolo_input_size", YOLO_INPUT_SIZE)
        img = cv2.resize(frame, (input_size, input_size))

        if self._use_onnx:
            inp = img[:, :, ::-1].astype(np.float32) / 255.0   # BGR→RGB
            inp = inp.transpose(2, 0, 1)
            inp = np.expand_dims(inp, 0)
            inp = np.ascontiguousarray(inp)
            # Cast to float16 if the model requires it
            if hasattr(self, "_yolo_dtype") and "float16" in str(self._yolo_dtype):
                inp = inp.astype(np.float16)
            raw = self._yolo.run(None, {self._yolo_input_name: inp})[0]
            # Ensure output is float32 for postprocessing
            if raw.dtype != np.float32:
                raw = raw.astype(np.float32)
        elif getattr(self, "_use_cv2dnn", False):
            blob = cv2.dnn.blobFromImage(
                img, 1 / 255.0, (YOLO_INPUT_SIZE, YOLO_INPUT_SIZE),
                swapRB=True, crop=False
            )
            self._dnn_net.setInput(blob)
            raw = self._dnn_net.forward()
        else:
            return None

        return raw

    def _yolo_postprocess(self, output: np.ndarray,
                           orig_h: int, orig_w: int):
        """Parse raw YOLOv5 output tensor (1, N, 85) → detections."""
        preds = output[0] if output.ndim == 3 else output
        obj_conf = preds[:, 4]
        mask = obj_conf > YOLO_CONF_THRESHOLD
        preds = preds[mask]
        if len(preds) == 0:
            return []

        class_scores = preds[:, 5:] * preds[:, 4:5]
        class_ids = class_scores.argmax(axis=1)
        scores = class_scores[np.arange(len(class_ids)), class_ids]

        valid = [
            i for i in range(len(scores))
            if scores[i] >= YOLO_CONF_THRESHOLD and int(class_ids[i]) in OBSTACLE_CLASS_IDS
        ]
        if not valid:
            return []

        preds = preds[valid]
        scores = scores[valid]
        class_ids = class_ids[valid]

        cx, cy, w, h = preds[:, 0], preds[:, 1], preds[:, 2], preds[:, 3]
        x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        boxes = np.stack([x1, y1, x2, y2], axis=1)

        keep = _nms(boxes, scores, YOLO_IOU_THRESHOLD)
        results = []
        # Scale box back to original frame using actual input size used
        sx = orig_w / getattr(self, "_yolo_input_size", YOLO_INPUT_SIZE)
        sy = orig_h / getattr(self, "_yolo_input_size", YOLO_INPUT_SIZE)
        for k in keep:
            bx1 = int(np.clip(boxes[k, 0] * sx, 0, orig_w - 1))
            by1 = int(np.clip(boxes[k, 1] * sy, 0, orig_h - 1))
            bx2 = int(np.clip(boxes[k, 2] * sx, 0, orig_w - 1))
            by2 = int(np.clip(boxes[k, 3] * sy, 0, orig_h - 1))
            results.append((np.array([bx1, by1, bx2, by2]),
                            float(scores[k]), int(class_ids[k])))
        return results

    # ── Zone classification ───────────────────────────────────────────────

    @staticmethod
    def _classify_zone(cx: int, frame_w: int) -> str:
        scaled = int(cx * 320 / frame_w) if frame_w != 320 else cx
        if scaled < ZONE_LEFT_END:
            return "left"
        elif scaled < ZONE_CENTER_END:
            return "center"
        else:
            return "right"

    # ── Main pipeline ─────────────────────────────────────────────────────

    def process_frame(self, frame: np.ndarray | None = None) -> VisionResult:
        """
        Run the full vision pipeline on one frame.
        If frame is None, capture from BLE phone / USB webcam / simulator.
        """
        t0 = time.monotonic()
        result = VisionResult()

        source = "external"
        if frame is None:
            frame, source = self.capture_frame()
        if frame is None:
            logger.warning("No frame available — returning empty result")
            return result

        result.source = source
        result.frame = frame.copy()
        orig_h, orig_w = frame.shape[:2]

        # ── YOLO inference ────────────────────────────────────────────────
        raw = self._run_yolo(frame)
        if raw is not None:
            detections = self._yolo_postprocess(raw, orig_h, orig_w)
        else:
            detections = []

        # ── Fuse detections with heuristic depth ──────────────────────────
        for bbox, conf, cls_id in detections:
            x1, y1, x2, y2 = bbox
            dist = _estimate_depth_from_bbox((x1, y1, x2, y2), orig_h, orig_w)
            cx = (x1 + x2) // 2
            zone = self._classify_zone(cx, orig_w)
            label = OBSTACLE_CLASS_IDS.get(cls_id, f"class_{cls_id}")
            obs = ObstacleInfo(
                label=label,
                confidence=conf,
                distance_m=round(dist, 2),
                zone=zone,
                bbox=(x1, y1, x2, y2),
            )
            result.obstacles.append(obs)
            if dist < result.zone_min_dist[zone]:
                result.zone_min_dist[zone] = dist
            if dist < result.closest_distance:
                result.closest_distance = dist

        # ── Determine recommended action ──────────────────────────────────
        left_d  = result.zone_min_dist["left"]
        center_d = result.zone_min_dist["center"]
        right_d = result.zone_min_dist["right"]

        if result.closest_distance > DEPTH_DANGER_THRESHOLD:
            result.recommended_action = "clear"
        elif (left_d   < DEPTH_EMERGENCY_THRESHOLD and
              center_d < DEPTH_EMERGENCY_THRESHOLD and
              right_d  < DEPTH_EMERGENCY_THRESHOLD):
            result.recommended_action = "stop"
        elif center_d < DEPTH_DANGER_THRESHOLD:
            result.recommended_action = "steer_left" if left_d > right_d else "steer_right"
        elif left_d < DEPTH_DANGER_THRESHOLD:
            result.recommended_action = "steer_right"
        elif right_d < DEPTH_DANGER_THRESHOLD:
            result.recommended_action = "steer_left"
        else:
            result.recommended_action = "clear"

        result.frame_time_ms = (time.monotonic() - t0) * 1000.0
        return result

    # ── Cleanup ───────────────────────────────────────────────────────────

    def release(self):
        """Release camera resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera released")

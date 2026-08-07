"""
config.py — Central configuration for the Nemo~Sense Navigational Aid Rover.

All tuneable constants collected here. Designed for:
  - Arduino UNO Q (Qualcomm Dragonwing) running Debian Linux
  - STM32 co-processor connected via /dev/ttyACM0
  - Logitech 720p USB webcam on /dev/video0 via USB hub
  - Quarky chassis receiving GPIO signals on pins 1/2/3
"""

from __future__ import annotations
import os

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR   = os.path.join(PROJECT_ROOT, "models")

# ---------------------------------------------------------------------------
# Bridge serial (Linux ↔ STM32 MCU — internal UART, always available)
# On the Arduino UNO Q, the STM32 co-processor is exposed to Linux
# via the internal high-speed UART: /dev/ttyHS1
# This does NOT require any USB cable — it is wired inside the board.
# ---------------------------------------------------------------------------
SERIAL_PORT = "/dev/ttyHS1"
SERIAL_BAUD = 115200

# Motor backend
MOTOR_BACKEND        = "router_bridge"   # UNO Q Linux → STM32 MCU → Quarky GPIO
COMMAND_INTERVAL_S   = 0.25             # seconds between motor command sends
MCU_WATCHDOG_MS      = 1000            # MCU-side watchdog timeout (ms)

# ---------------------------------------------------------------------------
# Camera / capture
# ---------------------------------------------------------------------------
CAMERA_INDEX  = 0      # /dev/video0 — Logitech 720p on USB hub
CAMERA_WIDTH  = 320    # YOLOv5n input (downsampled from 720p)
CAMERA_HEIGHT = 320
CAMERA_FPS    = 15     # 720p @ 15fps is comfortable for the Cortex-A53

# ---------------------------------------------------------------------------
# ONNX model paths
# ---------------------------------------------------------------------------
YOLO_MODEL_PATH  = os.path.join(MODELS_DIR, "yolov5n.onnx")
MIDAS_MODEL_PATH = os.path.join(MODELS_DIR, "midas_small.onnx")

# ---------------------------------------------------------------------------
# YOLOv5n inference
# ---------------------------------------------------------------------------
YOLO_INPUT_SIZE      = 320
YOLO_CONF_THRESHOLD  = 0.45
YOLO_IOU_THRESHOLD   = 0.45
ONNX_THREADS         = 4      # Cortex-A53 has 4 cores

# COCO class IDs that are relevant obstacles for a sidewalk rover
OBSTACLE_CLASS_IDS = {
    0:  "person",
    1:  "bicycle",
    2:  "car",
    3:  "motorcycle",
    5:  "bus",
    7:  "truck",
    9:  "traffic light",
    10: "fire hydrant",
    11: "stop sign",
    13: "bench",
    14: "bird",
    15: "cat",
    16: "dog",
    24: "backpack",
    25: "umbrella",
    28: "suitcase",
    56: "chair",
    57: "couch",
    58: "potted plant",
    60: "dining table",
    63: "laptop",
}

# ---------------------------------------------------------------------------
# Depth estimation
# ---------------------------------------------------------------------------
MIDAS_INPUT_SIZE           = 256
DEPTH_SCALE                = 3.0    # metres ≈ DEPTH_SCALE / relative_depth
DEPTH_OFFSET               = 0.0
DEPTH_DANGER_THRESHOLD     = 1.5   # metres → slow / steer
DEPTH_EMERGENCY_THRESHOLD  = 0.5   # metres → full stop

# ---------------------------------------------------------------------------
# Frame zone boundaries (320-px wide frame)
# ---------------------------------------------------------------------------
ZONE_LEFT_END   = 106   # columns [0,   106)
ZONE_CENTER_END = 214   # columns [106, 214) — [214,320) = right

# ---------------------------------------------------------------------------
# Speed / motor parameters
# ---------------------------------------------------------------------------
MIN_SPEED     = 0.1    # m/s
MAX_SPEED     = 0.8    # m/s
DEFAULT_SPEED = 0.3    # m/s (conservative for indoor/campus use)

# Linear PWM mapping:  PWM = K * speed + B
# 0.1 m/s → ~60 PWM,  0.8 m/s → ~220 PWM
SPEED_TO_PWM_K = 228.57
SPEED_TO_PWM_B = 37.14
PWM_MIN = 0
PWM_MAX = 255

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
WAYPOINT_REACHED_RADIUS_M = 10.0     # metres — "close enough" to advance
EARTH_RADIUS_M            = 6_371_000.0

# ---------------------------------------------------------------------------
# WiFi sensing — DISABLED (camera-only build)
# ---------------------------------------------------------------------------
WIFI_SENSING_ENABLED         = False
WIFI_RSSI_REFERENCE          = -40.0
WIFI_PATH_LOSS_EXPONENT      = 2.7
WIFI_SHADOW_FADE_THRESHOLD_DB= 6.0
WIFI_BEACON_INTERVAL_S       = 0.5
WIFI_KALMAN_PROCESS_NOISE    = 0.1
WIFI_KALMAN_MEASUREMENT_NOISE= 2.0
WIFI_OCCUPANCY_GRID_SIZE     = 8
WIFI_OCCUPANCY_CELL_SIZE_M   = 0.5
WIFI_ROUTER_BSSID            = ""
WIFI_ROUTER_SSID             = ""

# Sensor fusion weights (kept for future use)
FUSION_VISION_WEIGHT = 1.0
FUSION_WIFI_WEIGHT   = 0.0

def speed_to_pwm(speed_ms: float) -> int:
    """Convert a speed in m/s to a PWM value [0, 255]."""
    if abs(speed_ms) < 0.01:
        return 0
    pwm = int(SPEED_TO_PWM_K * abs(speed_ms) + SPEED_TO_PWM_B)
    return max(PWM_MIN, min(PWM_MAX, pwm))

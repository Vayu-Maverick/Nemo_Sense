#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# download_models.sh — Download ONNX models for the Netra rover
#
# Downloads:
#   1. YOLOv5n  (object detection, ~4 MB)
#   2. MiDaS Small / v2.1 small  (monocular depth, ~17 MB)
#
# Models are placed in  python/models/  relative to this script's parent.
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MODELS_DIR="${PROJECT_ROOT}/python/models"

mkdir -p "$MODELS_DIR"

# ── Helper: download with wget, fallback to curl ─────────────────────────
download() {
    local url="$1"
    local dest="$2"

    if [ -f "$dest" ]; then
        echo "[✓] Already exists: $(basename "$dest")"
        return 0
    fi

    echo "[↓] Downloading $(basename "$dest") …"
    if command -v wget &>/dev/null; then
        wget -q --show-progress -O "$dest" "$url"
    elif command -v curl &>/dev/null; then
        curl -L --progress-bar -o "$dest" "$url"
    else
        echo "[✗] Neither wget nor curl found.  Install one and re-run."
        exit 1
    fi
    echo "[✓] Saved: $dest"
}

# ── 1. YOLOv5n ONNX ──────────────────────────────────────────────────────
YOLO_URL="https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.onnx"
YOLO_DEST="${MODELS_DIR}/yolov5n.onnx"
download "$YOLO_URL" "$YOLO_DEST"

# ── 2. MiDaS Small ONNX ──────────────────────────────────────────────────
# The official isl-org/MiDaS repo publishes .pt weights.  The community-
# maintained ONNX export is hosted on GitHub releases.  We use the v2.1
# small model which is well-suited for ARM inference.
MIDAS_URL="https://github.com/isl-org/MiDaS/releases/download/v2_1/midas_v21_small_256.onnx"
MIDAS_DEST="${MODELS_DIR}/midas_small.onnx"
download "$MIDAS_URL" "$MIDAS_DEST"

echo ""
echo "All models downloaded to: ${MODELS_DIR}"
ls -lh "$MODELS_DIR"

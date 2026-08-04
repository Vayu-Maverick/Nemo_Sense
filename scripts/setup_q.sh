#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# setup_q.sh — One-time setup for the Netra rover on Arduino UNO Q
#
# Run as root (or with sudo) on the Q's Debian Linux.
#
# Steps:
#   1. Install system packages (OpenCV, Bluetooth dev libs, Python, etc.)
#   2. Create a Python virtual environment
#   3. Install pip requirements
#   4. Enable and start the Bluetooth service
#   5. Make the Q discoverable
#   6. Download ONNX models
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_ROOT}/venv"

echo "════════════════════════════════════════════════════════════════"
echo "  Netra Blind Guide Rover — UNO Q Setup"
echo "════════════════════════════════════════════════════════════════"

# ── 1. System packages ───────────────────────────────────────────────────
echo ""
echo "[1/6] Installing system packages …"
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libopencv-dev \
    python3-opencv \
    bluetooth \
    bluez \
    libbluetooth-dev \
    portaudio19-dev \
    wget \
    curl \
    git

echo "[✓] System packages installed"

# ── 2. Create Python virtual environment ─────────────────────────────────
echo ""
echo "[2/6] Creating Python venv at ${VENV_DIR} …"
if [ -d "$VENV_DIR" ]; then
    echo "     (venv already exists, skipping creation)"
else
    python3 -m venv --system-site-packages "$VENV_DIR"
fi

# Activate venv
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
echo "[✓] venv activated ($(python3 --version))"

# ── 3. Install pip requirements ──────────────────────────────────────────
echo ""
echo "[3/6] Installing Python dependencies …"
pip install --upgrade pip setuptools wheel
pip install -r "${PROJECT_ROOT}/requirements.txt"
echo "[✓] pip requirements installed"

# ── 4. Enable Bluetooth ──────────────────────────────────────────────────
echo ""
echo "[4/6] Enabling Bluetooth service …"
systemctl enable bluetooth
systemctl start bluetooth
echo "[✓] Bluetooth service active"

# ── 5. Make discoverable ─────────────────────────────────────────────────
echo ""
echo "[5/6] Making device discoverable …"
# Set the Bluetooth adapter name and make it discoverable.
# The 'timeout 0' means it stays discoverable permanently.
hciconfig hci0 up 2>/dev/null || true
bluetoothctl <<EOF
power on
discoverable on
agent NoInputNoOutput
default-agent
EOF
echo "[✓] Bluetooth discoverable"

# ── 6. Download ONNX models ──────────────────────────────────────────────
echo ""
echo "[6/6] Downloading ONNX models …"
bash "${SCRIPT_DIR}/download_models.sh"

# ── 7. Configure Auto-Boot Service ───────────────────────────────────────
echo ""
echo "[7/7] Configuring systemd auto-boot service …"
cat << 'SERVICE_EOF' > /etc/systemd/system/netra-brain.service
[Unit]
Description=Netra Autonomous Brain
After=network.target bluetooth.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/netra
ExecStart=/root/netra/venv/bin/python /root/netra/q_brain.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable netra-brain.service
systemctl start netra-brain.service
echo "[✓] Auto-boot service installed and started!"

# ── Done ──────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  To run Netra:"
echo "    source ${VENV_DIR}/bin/activate"
echo "    cd ${PROJECT_ROOT}/python"
echo "    python main.py --mode full"
echo ""
echo "  To test motors only:"
echo "    python main.py --mode motor-test"
echo "════════════════════════════════════════════════════════════════"

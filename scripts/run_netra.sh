#!/usr/bin/env bash
# run_netra.sh — Start GuideSense on the Arduino UNO Q
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/venv"

if [ -d "$VENV" ]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
fi

cd "${ROOT}/python"
MODE="${1:-indoor}"
echo "Starting GuideSense in mode: ${MODE}"
exec python3 main.py --mode "${MODE}"

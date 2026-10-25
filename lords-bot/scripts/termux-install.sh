#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

if ! command -v pkg >/dev/null 2>&1; then
  echo "Run this script inside Termux." >&2
  exit 1
fi

cd "$(dirname "$0")/.."

echo "Updating Termux packages..."
pkg update -y
pkg install -y python android-tools libyaml

echo "Installing NumPy and OpenCV from Termux packages..."
pkg install -y x11-repo
pkg update -y
pkg install -y python-numpy opencv-python

echo "Installing Python dependencies..."
python -m pip install --upgrade pip setuptools wheel
pkg install -y python-pyyaml || python -m pip install PyYAML
if python -m pip install -e . --no-deps; then
  echo "Installed the lordsbot command."
else
  echo "Editable install failed; scripts/termux-run.sh still works."
fi

python - <<'PY'
import cv2
import numpy
import yaml

print(f"OpenCV {cv2.__version__} | NumPy {numpy.__version__} | PyYAML {yaml.__version__}")
PY

if [ ! -f config.yaml ]; then
  cp config.example.yaml config.yaml
fi

termux-wake-lock || true

echo
echo "Next: enable Wireless debugging, then run"
echo "  bash scripts/termux-connect.sh"
echo "Then:"
echo "  bash scripts/termux-run.sh run --task rotation --dry-run --once"

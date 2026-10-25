#!/data/data/com.termux/files/usr/bin/bash
set -uo pipefail

cd "$(dirname "$0")/.."

if ! command -v adb >/dev/null 2>&1; then
  echo "adb is missing; run scripts/termux-install.sh first." >&2
  exit 1
fi

termux-wake-lock || true
python -m lordsbot "$@"
status=$?
termux-wake-unlock || true
exit "$status"

#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

if ! command -v adb >/dev/null 2>&1; then
  echo "adb is missing; run scripts/termux-install.sh first." >&2
  exit 1
fi

echo "Enable Settings > Developer options > Wireless debugging first."
adb start-server >/dev/null

read -r -p "Pair a new device? [y/N] " pair
if [[ "${pair:-N}" =~ ^[Yy]$ ]]; then
  read -r -p "Pairing port: " pair_port
  read -r -p "Six-digit pairing code: " pair_code
  adb pair "127.0.0.1:${pair_port}" "${pair_code}"
fi

read -r -p "Connection port: " connect_port
adb connect "127.0.0.1:${connect_port}"
adb devices
adb shell getprop ro.product.model

read -r -p "Disable phantom process killing for long runs? [y/N] " phantom
if [[ "${phantom:-N}" =~ ^[Yy]$ ]]; then
  adb shell settings put global settings_enable_monitor_phantom_procs false
fi

read -r -p "Keep the screen awake while charging? [y/N] " stayon
if [[ "${stayon:-N}" =~ ^[Yy]$ ]]; then
  adb shell svc power stayon true
fi

echo
echo "Connected. Start with a dry run:"
echo "  bash scripts/termux-run.sh run --task rotation --dry-run --once"

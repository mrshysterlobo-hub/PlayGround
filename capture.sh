#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PROJECT_DIR="$(pwd)"
: "${CAPTURE_URL:?Set CAPTURE_URL to the exact preview URL}"
CAPTURE_DIR="${CAPTURE_DIR:-${OPENCODE_WEB_DIR:-/tmp}/captures}"

case "$CAPTURE_DIR" in
  "$PROJECT_DIR"|"$PROJECT_DIR"/*)
    echo "CAPTURE_DIR must be outside the source tree: $CAPTURE_DIR" >&2
    exit 1
    ;;
esac

export CAPTURE_URL CAPTURE_DIR

/usr/bin/time -p mkdir -p "$CAPTURE_DIR"

set +e
/usr/bin/time -p node capture.mjs
capture_status=$?
set -e

if [[ "$capture_status" -ne 0 ]]; then
  echo "Capture failed with exit code $capture_status" >&2
  exit "$capture_status"
fi

/usr/bin/time -p test -s "$CAPTURE_DIR/final-desktop.png"
/usr/bin/time -p test -s "$CAPTURE_DIR/final-mobile.png"
/usr/bin/time -p ls -lh "$CAPTURE_DIR/final-desktop.png" "$CAPTURE_DIR/final-mobile.png"

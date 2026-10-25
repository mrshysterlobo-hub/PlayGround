#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PROJECT_DIR="$(pwd)"
PORT="${PORT:-3000}"
DIST_DIR="$PROJECT_DIR/dist"
META_DIR="${OPENCODE_WEB_DIR:-/home/runner/work/_temp/omgithub-web}"
export PORT

/usr/bin/time -p mkdir -p "$META_DIR"

if [[ -f package.json ]]; then
  /usr/bin/time -p npm install --no-audit --no-fund --ignore-scripts
fi

/usr/bin/time -p node build.mjs

/usr/bin/time -p test -f "$DIST_DIR/index.html"
/usr/bin/time -p printf '{"project":"%s","directory":"%s"}' "$PROJECT_DIR" "$DIST_DIR" > "$META_DIR/deployment-output.json"
/usr/bin/time -p cat "$META_DIR/deployment-output.json"

echo "Serving $DIST_DIR on port $PORT"
exec /usr/bin/time -p node serve.mjs

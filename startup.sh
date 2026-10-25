#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

RUNTIME_DIR="${RUNTIME_DIR:-/home/runner/work/_temp/omgithub-runtime}"
PLAYWRIGHT_ROOT="$HOME/.local/share/omgithub-playwright"

/usr/bin/time -p node --version
/usr/bin/time -p test -f package.json
/usr/bin/time -p test -x /usr/local/bin/playwright-cli

if [[ ! -x "$PLAYWRIGHT_ROOT/node_modules/.bin/playwright" || ! -s "$PLAYWRIGHT_ROOT/display" ]]; then
  /usr/bin/time -p bash "$RUNTIME_DIR/scripts/setup-linux-playwright.sh"
fi

/usr/bin/time -p test -x "$PLAYWRIGHT_ROOT/node_modules/.bin/playwright"
/usr/bin/time -p test -s "$PLAYWRIGHT_ROOT/display"

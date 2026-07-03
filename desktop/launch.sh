#!/usr/bin/env bash
# Launch the WarrantyLens desktop app. Installs Electron on first run.
set -uo pipefail
cd "$(dirname "$0")"

if [ ! -d node_modules/electron ]; then
  echo "[WarrantyLens] First run: installing the desktop app (one-time, downloads Electron)…"
  npm install --no-audit --no-fund || { echo "npm install failed"; read -rp "Enter to close…"; exit 1; }
fi

exec ./node_modules/.bin/electron . --no-sandbox

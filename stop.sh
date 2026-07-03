#!/usr/bin/env bash
# Stop the WarrantyLens stack (data is preserved in Docker volumes).
set -uo pipefail
cd "$(dirname "$0")"

if docker info >/dev/null 2>&1; then RUN() { bash -c "$1"; }
else RUN() { sg docker -c "$1"; }; fi

echo "[WarrantyLens] Stopping services…"
RUN "docker compose down"
echo "[WarrantyLens] Stopped. Data preserved. Run ./run.sh to start again."

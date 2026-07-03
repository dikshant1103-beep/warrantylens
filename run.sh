#!/usr/bin/env bash
# WarrantyLens launcher: bring up the stack and open the dashboard.
set -uo pipefail
cd "$(dirname "$0")"

GREEN='\033[0;32m'; RED='\033[0;31m'; YEL='\033[1;33m'; NC='\033[0m'
say() { echo -e "${GREEN}[WarrantyLens]${NC} $*"; }
warn() { echo -e "${YEL}[WarrantyLens]${NC} $*"; }
die() { echo -e "${RED}[WarrantyLens] $*${NC}"; echo; read -rp "Press Enter to close…"; exit 1; }

# 1) Docker present?
if ! command -v docker >/dev/null 2>&1; then
  die "Docker is not installed.
Install it once with:
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker \$USER   # then log out/in once
Then double-click this launcher again."
fi

# 2) Find a working way to call docker.
#    Direct first; if the session lacks the docker group (no re-login since
#    install), fall back to 'sg docker' which reads group membership live.
if docker info >/dev/null 2>&1; then
  RUN() { bash -c "$1"; }
elif getent group docker | grep -qw "$USER" && sg docker -c "docker info" >/dev/null 2>&1; then
  warn "Using 'sg docker' (log out/in once to make this permanent)."
  RUN() { sg docker -c "$1"; }
else
  die "Docker is installed but this session can't access it.
Easiest fix: log out and back in once (you were added to the 'docker' group).
Or run:  sudo systemctl start docker"
fi

# 3) First-run env files
[ -f .env ] || cp .env.example .env
[ -f backend/.env ] || cp backend/.env.example backend/.env

# 4) Bring up the stack
say "Starting services (first run builds images — can take a few minutes)…"
RUN "docker compose up -d --build" || die "docker compose failed to start. See: docker compose logs"

# 5) Wait for the API to be healthy
say "Waiting for the API to come up…"
for i in $(seq 1 90); do
  if curl -fsS http://localhost:8000/api/v1/health >/dev/null 2>&1; then ok=1; break; fi
  sleep 2
done
[ "${ok:-0}" = 1 ] || die "API did not become healthy. Check: docker compose logs api"

# 6) First-time DB migrate + seed (idempotent)
say "Applying migrations + seeding demo data…"
RUN "docker compose exec -T api alembic upgrade head" || warn "migration step reported an issue"
RUN "docker compose exec -T api python -m app.scripts.seed" || warn "seed step reported an issue"

# 7) Open the dashboard
URL="http://localhost:3000"
say "Opening the dashboard: $URL"
say "Login: admin@demo.warrantylens.io  /  Admin12345!"
( command -v xdg-open >/dev/null && xdg-open "$URL" ) || \
  ( command -v sensible-browser >/dev/null && sensible-browser "$URL" ) || \
  warn "Open $URL in your browser."

echo
say "Stack is running. Close this window to leave it running, or run ./stop.sh to stop it."
read -rp "Press Enter to close this window…"

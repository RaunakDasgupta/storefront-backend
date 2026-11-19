#!/usr/bin/env bash
# Start the API and the frontend together, for a demo.
#   ./scripts/run-all.sh                       # the frontend is expected next to this repo (../storefront-frontend)
#   FRONTEND_DIR=/path/to/storefront-frontend API_PORT=8000 ./scripts/run-all.sh
# Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."

FRONTEND_DIR="${FRONTEND_DIR:-../storefront-frontend}"
API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
# what the browser uses to reach the API: set API_PUBLIC_URL if you open the demo from another machine
API_PUBLIC_URL="${API_PUBLIC_URL:-http://localhost:${API_PORT}}"

[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example. Set DATABASE_URL in it, then run this again."; exit 1; }
[ -d "$FRONTEND_DIR" ] || { echo "Frontend folder not found: $FRONTEND_DIR (set FRONTEND_DIR)"; exit 1; }
[ -d .venv ] || { echo "No .venv yet: run 'make install' first."; exit 1; }
[ -d "$FRONTEND_DIR/node_modules" ] || (cd "$FRONTEND_DIR" && npm install)

pids=()
cleanup() { for pid in "${pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

echo "API       -> http://localhost:${API_PORT}/docs"
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT" &
pids+=($!)

echo "Storefront -> http://localhost:${FRONTEND_PORT}   Admin -> http://localhost:${FRONTEND_PORT}/admin"
(cd "$FRONTEND_DIR" && VITE_API_URL="${API_PUBLIC_URL}/api/v1" npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT") &
pids+=($!)

wait

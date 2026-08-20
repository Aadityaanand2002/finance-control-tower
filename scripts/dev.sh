#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Starting Finance Control Tower (local demo)..."
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  python3.12 -m venv .venv || python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

PYTHONPATH=. uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACK_PID=$!
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm install
fi
npm run dev -- --host 127.0.0.1 --port 5173 &
FRONT_PID=$!

trap 'kill $BACK_PID $FRONT_PID 2>/dev/null || true' EXIT
echo "Backend http://127.0.0.1:8000  Frontend http://127.0.0.1:5173"
wait

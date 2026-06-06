#!/usr/bin/env bash
# Start all Hoops dev services: API (8000), ws_bridge (8765), frontend (5173).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

kill_port() {
  local port=$1
  local pids
  pids=$(lsof -ti:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "Stopping port $port (pids: $pids)"
    kill $pids 2>/dev/null || true
    sleep 1
    pids=$(lsof -ti:"$port" 2>/dev/null || true)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
  fi
}

echo "==> Hoops dev stack from $ROOT"
kill_port 8000
kill_port 8765
kill_port 5173

echo "==> API :8000"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --loop asyncio &
API_PID=$!

echo "==> ws_bridge :8765"
python3 ws_bridge.py &
WS_PID=$!

echo "==> frontend :5173"
cd frontend && npm run dev &
UI_PID=$!

cleanup() {
  echo "Stopping..."
  kill $API_PID $WS_PID $UI_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo "Ready:"
echo "  UI:        http://localhost:5173"
echo "  API:       http://localhost:8000"
echo "  ws_bridge: http://localhost:8765"
echo "Press Ctrl+C to stop all."
wait

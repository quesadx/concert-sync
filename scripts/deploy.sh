#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-9999}"
MODE="${1:-server}"

echo "=== ConcertSync Deployment ==="
echo "Host: $HOST"
echo "Port: $PORT"
echo "Mode: $MODE"
echo ""

# Ensure clean DB (optional: set PRESERVE_DB=1 to keep session state)
if [[ "${PRESERVE_DB:-0}" != "1" ]]; then
    rm -f data/concert_sync.db
    echo "  → Database reset (clean start)"
fi

mkdir -p logs

case "$MODE" in
    server)
        echo "  Starting server..."
        uv run python main.py --host "$HOST" --port "$PORT"
        ;;
    background)
        echo "  Starting server in background..."
        nohup uv run python main.py --host "$HOST" --port "$PORT" > logs/server.log 2>&1 &
        SERVER_PID=$!
        echo "  Server PID: $SERVER_PID"
        echo "  Log: logs/server.log"
        echo "  To stop: kill $SERVER_PID"
        ;;
    load-test)
        echo "  Running load test..."
        uv run python tests/load_generator.py --host "$HOST" --port "$PORT" --requests 100 --conflicts
        ;;
    stress-test)
        echo "  Running stress test..."
        uv run python tests/load_generator.py --host "$HOST" --port "$PORT" --requests 500 --conflicts
        ;;
    health)
        echo "  Checking server health..."
        uv run python -c "
import socket, json
s = socket.socket()
s.settimeout(5)
s.connect(('$HOST', $PORT))
s.send(json.dumps({'action': 'QUERY'}).encode())
resp = s.recv(4096).decode()
data = json.loads(resp)
print(f'Status: {data.get(\"status\")}')
print(f'Sections: {data.get(\"sections\", {})}')
s.close()
"
        ;;
    *)
        echo "Usage: $0 [server|background|load-test|stress-test|health]"
        exit 1
        ;;
esac

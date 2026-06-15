#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-server}"
shift || true

SERVER_PID=""
PYTHON_BIN=""
USE_UV=0

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}

ensure_python_bin() {
  if [[ -n "$PYTHON_BIN" ]]; then
    return 0
  fi

  if command -v uv >/dev/null 2>&1; then
    USE_UV=1
    PYTHON_BIN="uv run python"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
    return 0
  fi

  printf 'error: python3 is required when uv is not installed.\n' >&2
  exit 1
}

ensure_venv() {
  if [[ "$USE_UV" -eq 1 ]]; then
    uv sync --group dev --group tui
    return 0
  fi

  if [[ ! -x .venv/bin/python ]]; then
    "$PYTHON_BIN" -m venv .venv
  fi

  .venv/bin/python -m pip install --upgrade pip >/dev/null
}

run_python() {
  if [[ "$USE_UV" -eq 1 ]]; then
    uv run python "$@"
  else
    .venv/bin/python "$@"
  fi
}

ensure_package() {
  local package_name="$1"

  if [[ "$USE_UV" -eq 1 ]]; then
    return 0
  fi

  if ! .venv/bin/python - "$package_name" <<'PY'
import importlib.util
import sys

module_name = sys.argv[1]
sys.exit(0 if importlib.util.find_spec(module_name) else 1)
PY
  then
    .venv/bin/python -m pip install "$package_name"
  fi
}

wait_for_server() {
  local attempts=50
  local attempt=0
  local checker

  if [[ "$USE_UV" -eq 1 ]]; then
    checker=(uv run python)
  else
    checker=(.venv/bin/python)
  fi

  while (( attempt < attempts )); do
    if "${checker[@]}" - <<'PY'
import socket
import sys

sock = socket.socket()
sock.settimeout(0.2)
try:
    sock.connect(("127.0.0.1", 9999))
except OSError:
    sys.exit(1)
finally:
    sock.close()
sys.exit(0)
PY
    then
      return 0
    fi

    sleep 0.2
    attempt=$((attempt + 1))
  done

  return 1
}

if ! command -v uv >/dev/null 2>&1; then
  printf 'error: uv is required. Install it from https://docs.astral.sh/uv/ and try again.\n' >&2
  exit 1
fi

ensure_python_bin
ensure_venv

trap cleanup EXIT INT TERM

case "$MODE" in
  server)
    run_python main.py "$@"
    ;;
  tui)
    ensure_package textual
    run_python -m frontend_tui "$@"
    ;;
  both)
    ensure_package textual
    run_python main.py "$@" &
    SERVER_PID=$!

    if ! wait_for_server; then
      printf 'error: server did not become ready on port 9999\n' >&2
      exit 1
    fi

    run_python -m frontend_tui "$@"
    ;;
  client)
    run_python -m frontend_pyside6 --mode client "$@"
    ;;
  dashboard)
    run_python desktop_launcher.py --mode dashboard "$@"
    ;;
  multi)
    # Multi-client mode: start server, then launch 2 clients with delay
    run_python main.py "$@" &
    SERVER_PID=$!

    if ! wait_for_server; then
      printf 'error: server did not become ready on port 9999\n' >&2
      exit 1
    fi

    printf 'Launching first client...\n'
    run_python -m frontend_pyside6 --mode client "$@" &
    CLIENT1_PID=$!
    sleep 2

    printf 'Launching second client...\n'
    run_python -m frontend_pyside6 --mode client "$@" &
    CLIENT2_PID=$!

    printf 'Server + 2 clients running. Waiting for clients to exit...\n'
    wait "$CLIENT1_PID" || true
    wait "$CLIENT2_PID" || true
    ;;
  test)
    ensure_package pytest
    if [[ "$USE_UV" -eq 1 ]]; then
      uv run pytest "$@"
    else
      .venv/bin/python -m pytest "$@"
    fi
    ;;
  load-test)
    ensure_package pytest
    uv run python tests/load_generator.py "$@"
    ;;
  stress-test)
    ensure_package pytest
    uv run python tests/load_generator.py --requests 500 --conflicts "$@"
    ;;
  *)
    printf 'usage: %s [server|tui|both|client|dashboard|multi|test|load-test|stress-test] [args...]\n' "$0" >&2
    exit 2
    ;;
esac

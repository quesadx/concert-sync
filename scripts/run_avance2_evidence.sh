#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="artifacts/fase2/${TIMESTAMP}"
mkdir -p "$OUT_DIR"

printf "[fase2] Output directory: %s\n" "$OUT_DIR"

printf "[fase2] Running full test suite...\n"
nix develop -c pytest -q | tee "$OUT_DIR/pytest-full.txt"

printf "[fase2] Running focused TTL/race tests...\n"
nix develop -c pytest -q \
  tests/test_transaction_idempotency.py::test_confirm_fails_after_expiration \
  tests/test_transaction_races.py::test_confirm_vs_expire_keeps_consistency \
  tests/test_transaction_races.py::test_cancel_vs_expire_releases_once | tee "$OUT_DIR/pytest-ttl-races.txt"

printf "[fase2] Running concurrent stress scenario...\n"
: > logs/system.log
nix develop -c python tests/concurrent_tests.py | tee "$OUT_DIR/concurrent-stress.txt"

cp logs/system.log "$OUT_DIR/system.log"

printf "[fase2] Building log summary...\n"
{
  echo "log_line_count"
  wc -l "$OUT_DIR/system.log"
  echo
  echo "event_distribution"
  rg "\[RESERVE\]|\[CONFIRM\]|\[CANCEL\]|\[EXPIRE\]|\[SERVER\]|\[THREAD\]|\[ERROR\]" "$OUT_DIR/system.log" -o | sort | uniq -c
} | tee "$OUT_DIR/log-summary.txt"

printf "[fase2] Done. Artifacts generated at %s\n" "$OUT_DIR"

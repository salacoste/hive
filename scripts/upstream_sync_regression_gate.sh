#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== Upstream Sync Regression Gate =="

echo
echo "-- acceptance toolchain self-check --"
./scripts/acceptance_toolchain_self_check.sh

echo
echo "-- runtime parity --"
./scripts/check_runtime_parity.sh

echo
echo "-- backlog consistency --"
uv run python scripts/check_backlog_status_consistency.py

echo
echo "[ok] upstream regression gate completed"

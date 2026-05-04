#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROFILE="${HIVE_UPSTREAM_SYNC_GATE_PROFILE:-smoke}"
PROJECT_ID="${HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID:-default}"

if [[ "$PROFILE" != "smoke" && "$PROFILE" != "full" ]]; then
  echo "error: HIVE_UPSTREAM_SYNC_GATE_PROFILE must be smoke or full (got: $PROFILE)" >&2
  exit 2
fi

run_ops_command() {
  if command -v docker >/dev/null 2>&1; then
    ./scripts/hive_ops_run.sh "$@"
  else
    "$@"
  fi
}

ok=0
failed=0

run_step() {
  local name="$1"
  shift
  if "$@"; then
    echo "[ok] $name"
    ok=$((ok + 1))
  else
    echo "[fail] $name" >&2
    failed=$((failed + 1))
  fi
}

echo "== Upstream Sync Regression Gate =="
echo "profile=$PROFILE"
echo "project_id=$PROJECT_ID"
echo "docker_cli_available=$(command -v docker >/dev/null 2>&1 && echo true || echo false)"

echo
run_step "acceptance toolchain self-check" run_ops_command ./scripts/acceptance_toolchain_self_check.sh
run_step "runtime parity" run_ops_command env HIVE_RUNTIME_PARITY_PROJECT_ID="$PROJECT_ID" ./scripts/check_runtime_parity.sh
run_step "backlog consistency" run_ops_command uv run --no-project python scripts/check_backlog_status_consistency.py

if [[ "$PROFILE" == "full" ]]; then
  echo
  run_step "server api tests" \
    run_ops_command uv run --package framework pytest core/framework/server/tests/test_api.py -q
  run_step "telegram bridge tests" \
    run_ops_command uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q
  run_step "frontend unit tests" \
    run_ops_command npm --prefix core/frontend run test -- --run
  run_step "frontend build" \
    run_ops_command npm --prefix core/frontend run build
fi

echo
echo "== Upstream Sync Regression Gate summary: ok=$ok failed=$failed =="
if [[ "$failed" -gt 0 ]]; then
  exit 1
fi

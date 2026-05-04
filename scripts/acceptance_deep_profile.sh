#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROJECT_ID="${HIVE_ACCEPTANCE_PROJECT_ID:-default}"
PRINT_PLAN=false
REFRESH_BACKLOG=true

while [[ "$#" -gt 0 ]]; do
  arg="$1"
  shift
  case "$arg" in
    --project)
      if [[ "$#" -eq 0 ]]; then
        echo "error: --project requires value" >&2
        exit 2
      fi
      PROJECT_ID="$1"
      shift
      ;;
    --print-plan)
      PRINT_PLAN=true
      ;;
    --no-backlog-refresh)
      REFRESH_BACKLOG=false
      ;;
    *)
      echo "usage: $0 [--project <id>] [--print-plan] [--no-backlog-refresh]" >&2
      exit 2
      ;;
  esac
done

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

echo "== Acceptance Deep Profile =="
echo "project_id=$PROJECT_ID"
echo "refresh_backlog=$REFRESH_BACKLOG"
echo "docker_cli_available=$(command -v docker >/dev/null 2>&1 && echo true || echo false)"

if [[ "$PRINT_PLAN" == "true" ]]; then
  echo "[plan] Step 1: full-deep acceptance gate preset (container-first aware)"
  echo "[plan] Step 2: backlog status artifact refresh"
  echo "[plan] Step 3: acceptance ops summary (json)"
  exit 0
fi

run_step "acceptance gate full-deep preset" \
  run_ops_command env HIVE_ACCEPTANCE_PROJECT_ID="$PROJECT_ID" ./scripts/acceptance_gate_presets.sh full-deep

if [[ "$REFRESH_BACKLOG" == "true" ]]; then
  run_step "backlog status artifact refresh" \
    run_ops_command uv run --no-project python scripts/backlog_status_artifact.py --output docs/ops/backlog-status/latest.json
else
  echo "[skip] backlog status artifact refresh"
fi

run_step "acceptance ops summary (json)" \
  run_ops_command uv run --no-project python scripts/acceptance_ops_summary.py --json

echo "== Acceptance Deep Profile summary: ok=$ok failed=$failed =="
if [[ "$failed" -gt 0 ]]; then
  exit 1
fi


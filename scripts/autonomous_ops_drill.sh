#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SKIP_NETWORK="${HIVE_AUTONOMOUS_DRILL_SKIP_NETWORK:-false}"
SKIP_BACKUP="${HIVE_AUTONOMOUS_DRILL_SKIP_BACKUP:-false}"
SKIP_LOOP_SMOKE="${HIVE_AUTONOMOUS_DRILL_SKIP_LOOP_SMOKE:-false}"
DRILL_PROJECT_IDS="${HIVE_AUTONOMOUS_DRILL_PROJECT_IDS:-default}"
BASE_URL="${HIVE_BASE_URL:-http://localhost:${HIVE_CORE_PORT:-8787}}"
API_BASE="${BASE_URL%/}/api"
RESOLVED_DRILL_PROJECT_IDS="$DRILL_PROJECT_IDS"

ok=0
failed=0

step_ok() {
  local name="$1"
  echo "[ok] $name"
  ok=$((ok + 1))
}

step_fail() {
  local name="$1"
  local err="$2"
  echo "[fail] $name: $err" >&2
  failed=$((failed + 1))
}

run_step() {
  local name="$1"
  shift
  if "$@"; then
    step_ok "$name"
  else
    step_fail "$name" "command failed"
  fi
}

resolve_default_project_id() {
  if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
    return 1
  fi
  local projects_json
  projects_json="$(curl -fsS --max-time 10 "$API_BASE/projects" 2>/dev/null || true)"
  [[ -n "$projects_json" ]] || return 1

  local project_id
  project_id="$(echo "$projects_json" | jq -r '.default_project_id // empty' 2>/dev/null || true)"
  if [[ -z "$project_id" ]]; then
    project_id="$(echo "$projects_json" | jq -r '.projects[0].id // empty' 2>/dev/null || true)"
  fi
  [[ -n "$project_id" ]] || return 1
  echo "$project_id"
}

replace_default_token() {
  local ids_csv="$1"
  local replacement="$2"
  local output=()
  local item trimmed
  IFS=',' read -r -a items <<< "$ids_csv"
  for item in "${items[@]}"; do
    trimmed="$(echo "$item" | sed 's/^ *//;s/ *$//')"
    [[ -n "$trimmed" ]] || continue
    if [[ "$trimmed" == "default" ]]; then
      output+=("$replacement")
    else
      output+=("$trimmed")
    fi
  done
  (IFS=','; echo "${output[*]}")
}

echo "== Hive Autonomous Ops Drill =="
echo "root=$ROOT_DIR"
echo "skip_network=$SKIP_NETWORK skip_backup=$SKIP_BACKUP skip_loop_smoke=$SKIP_LOOP_SMOKE"
echo "drill_project_ids=$DRILL_PROJECT_IDS"
echo "base_url=$BASE_URL"

if [[ "$SKIP_NETWORK" != "true" && "$DRILL_PROJECT_IDS" == *"default"* ]]; then
  resolved_default_project_id="$(resolve_default_project_id || true)"
  if [[ -n "$resolved_default_project_id" ]]; then
    RESOLVED_DRILL_PROJECT_IDS="$(replace_default_token "$DRILL_PROJECT_IDS" "$resolved_default_project_id")"
    echo "resolved_drill_project_ids=$RESOLVED_DRILL_PROJECT_IDS (default -> $resolved_default_project_id)"
  else
    echo "[warn] could not resolve default project id from API; using drill_project_ids as-is"
  fi
fi

run_step "shell syntax: autonomous loop scripts" \
  bash -n scripts/autonomous_loop_tick.sh scripts/autonomous_ops_health_check.sh scripts/install_autonomous_loop_launchd.sh scripts/status_autonomous_loop_launchd.sh scripts/uninstall_autonomous_loop_launchd.sh

if [[ "$SKIP_NETWORK" != "true" ]]; then
  run_step "autonomous ops health check" ./scripts/autonomous_ops_health_check.sh
else
  echo "[skip] autonomous ops health check (network)"
fi

if [[ "$SKIP_BACKUP" != "true" ]]; then
  run_step "backup hive state" ./scripts/backup_hive_state.sh
  latest="$(ls -1t ~/.hive/backups/hive-state-*.tar.gz 2>/dev/null | head -n 1 || true)"
  if [[ -n "$latest" ]]; then
    run_step "restore dry-run latest backup" ./scripts/restore_hive_state.sh --archive "$latest" --dry-run
  else
    step_fail "restore dry-run latest backup" "no backup archive found"
  fi
else
  echo "[skip] backup/restore drill"
fi

if [[ "$SKIP_NETWORK" != "true" && "$SKIP_LOOP_SMOKE" != "true" ]]; then
  run_step "autonomous loop smoke (run-cycle)" \
    env HIVE_AUTONOMOUS_PROJECT_IDS="$RESOLVED_DRILL_PROJECT_IDS" HIVE_AUTONOMOUS_USE_RUN_CYCLE=true HIVE_AUTONOMOUS_USE_TICK_ALL=true ./scripts/autonomous_loop_tick.sh
else
  echo "[skip] autonomous loop smoke"
fi

echo "== Drill summary: ok=$ok failed=$failed =="
if [[ "$failed" -gt 0 ]]; then
  exit 1
fi
exit 0

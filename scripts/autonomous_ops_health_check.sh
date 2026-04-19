#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${HIVE_BASE_URL:-http://localhost:${HIVE_CORE_PORT:-8787}}"
API_BASE="${BASE_URL%/}/api"
TIMEOUT_SEC="${HIVE_AUTONOMOUS_HEALTH_TIMEOUT:-15}"
PROJECT_ID="${HIVE_AUTONOMOUS_HEALTH_PROJECT_ID:-}"
PROFILE="${HIVE_AUTONOMOUS_HEALTH_PROFILE:-local}"
MAX_STUCK_RUNS="${HIVE_AUTONOMOUS_HEALTH_MAX_STUCK_RUNS:-}"
MAX_NO_PROGRESS_PROJECTS="${HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS:-}"
ALLOW_LOOP_STALE="${HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE:-}"

case "$PROFILE" in
  local|dev)
    : "${MAX_STUCK_RUNS:=2}"
    : "${MAX_NO_PROGRESS_PROJECTS:=2}"
    : "${ALLOW_LOOP_STALE:=true}"
    ;;
  staging)
    : "${MAX_STUCK_RUNS:=1}"
    : "${MAX_NO_PROGRESS_PROJECTS:=1}"
    : "${ALLOW_LOOP_STALE:=false}"
    ;;
  prod)
    : "${MAX_STUCK_RUNS:=0}"
    : "${MAX_NO_PROGRESS_PROJECTS:=0}"
    : "${ALLOW_LOOP_STALE:=false}"
    ;;
  *)
    echo "error: unsupported HIVE_AUTONOMOUS_HEALTH_PROFILE='$PROFILE' (use local|dev|staging|prod)" >&2
    exit 2
    ;;
esac

if ! command -v curl >/dev/null 2>&1; then
  echo "error: curl is required" >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required" >&2
  exit 2
fi

if ! [[ "$MAX_STUCK_RUNS" =~ ^[0-9]+$ ]]; then
  echo "error: HIVE_AUTONOMOUS_HEALTH_MAX_STUCK_RUNS must be an integer >= 0" >&2
  exit 2
fi
if ! [[ "$MAX_NO_PROGRESS_PROJECTS" =~ ^[0-9]+$ ]]; then
  echo "error: HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS must be an integer >= 0" >&2
  exit 2
fi

query="include_runs=true"
if [[ -n "$PROJECT_ID" ]]; then
  query="project_id=${PROJECT_ID}&${query}"
fi

resp=$(curl -fsS --max-time "$TIMEOUT_SEC" "$API_BASE/autonomous/ops/status?$query")

status=$(echo "$resp" | jq -r '.status // empty')
stuck_runs=$(echo "$resp" | jq -r '.alerts.stuck_runs_total // 0')
no_progress_projects=$(echo "$resp" | jq -r '.alerts.no_progress_projects_total // 0')
loop_stale=$(echo "$resp" | jq -r '.alerts.loop_stale // false')
loop_stale_seconds=$(echo "$resp" | jq -r '.alerts.loop_stale_seconds // 0')
runs_total=$(echo "$resp" | jq -r '.summary.runs_total // 0')
in_progress=$(echo "$resp" | jq -r '.summary.runs_by_status.in_progress // 0')
queued=$(echo "$resp" | jq -r '.summary.runs_by_status.queued // 0')

echo "ops_status=$status runs_total=$runs_total in_progress=$in_progress queued=$queued stuck_runs=$stuck_runs no_progress_projects=$no_progress_projects loop_stale=$loop_stale loop_stale_seconds=$loop_stale_seconds"
echo "profile=$PROFILE max_stuck_runs=$MAX_STUCK_RUNS max_no_progress_projects=$MAX_NO_PROGRESS_PROJECTS allow_loop_stale=$ALLOW_LOOP_STALE"

if [[ "$status" != "ok" ]]; then
  echo "error: ops status is not ok" >&2
  exit 1
fi
if (( stuck_runs > MAX_STUCK_RUNS )); then
  echo "error: stuck_runs_total=$stuck_runs exceeds max=$MAX_STUCK_RUNS" >&2
  exit 1
fi
if (( no_progress_projects > MAX_NO_PROGRESS_PROJECTS )); then
  echo "error: no_progress_projects_total=$no_progress_projects exceeds max=$MAX_NO_PROGRESS_PROJECTS" >&2
  exit 1
fi
if [[ "$ALLOW_LOOP_STALE" != "true" && "$loop_stale" == "true" ]]; then
  echo "error: loop_stale=true (set HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE=true to ignore)" >&2
  exit 1
fi

echo "ok: autonomous ops health check passed"

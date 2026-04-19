#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${HIVE_BASE_URL:-http://localhost:${HIVE_CORE_PORT:-8787}}"
API_BASE="${BASE_URL%/}/api"
TIMEOUT_SEC="${HIVE_AUTONOMOUS_REMEDIATE_TIMEOUT:-20}"
PROJECT_ID="${HIVE_AUTONOMOUS_REMEDIATE_PROJECT_ID:-}"
OLDER_THAN_SECONDS="${HIVE_AUTONOMOUS_REMEDIATE_OLDER_THAN_SECONDS:-1800}"
MAX_RUNS="${HIVE_AUTONOMOUS_REMEDIATE_MAX_RUNS:-100}"
ACTION="${HIVE_AUTONOMOUS_REMEDIATE_ACTION:-escalated}"
DRY_RUN="${HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN:-true}"
CONFIRM="${HIVE_AUTONOMOUS_REMEDIATE_CONFIRM:-false}"
REASON="${HIVE_AUTONOMOUS_REMEDIATE_REASON:-ops_script_remediation}"

if ! command -v curl >/dev/null 2>&1; then
  echo "error: curl is required" >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required" >&2
  exit 2
fi

payload=$(jq -n \
  --arg project_id "$PROJECT_ID" \
  --arg action "$ACTION" \
  --arg reason "$REASON" \
  --argjson older_than_seconds "$OLDER_THAN_SECONDS" \
  --argjson max_runs "$MAX_RUNS" \
  --argjson dry_run "$DRY_RUN" \
  --argjson confirm "$CONFIRM" \
  '{project_id:$project_id,action:$action,reason:$reason,older_than_seconds:$older_than_seconds,max_runs:$max_runs,dry_run:$dry_run,confirm:$confirm}')

resp=$(curl -sS --max-time "$TIMEOUT_SEC" -X POST \
  -H 'Content-Type: application/json' \
  -d "$payload" \
  "$API_BASE/autonomous/ops/remediate-stale")

echo "$resp" | jq .

#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${HIVE_BASE_URL:-http://localhost:${HIVE_CORE_PORT:-8787}}"
API_BASE="${BASE_URL%/}/api"
LOCK_FILE="${HIVE_AUTONOMOUS_LOOP_LOCK:-/tmp/hive-autonomous-loop.lock}"
LOCK_DIR_FALLBACK="${LOCK_FILE}.d"
PROJECT_IDS_RAW="${HIVE_AUTONOMOUS_PROJECT_IDS:-}"
AUTO_START="${HIVE_AUTONOMOUS_AUTO_START:-true}"
TIMEOUT_SEC="${HIVE_AUTONOMOUS_TICK_TIMEOUT:-20}"
USE_TICK_ALL="${HIVE_AUTONOMOUS_USE_TICK_ALL:-true}"
USE_RUN_CYCLE="${HIVE_AUTONOMOUS_USE_RUN_CYCLE:-true}"
MAX_STEPS_PER_PROJECT="${HIVE_AUTONOMOUS_MAX_STEPS_PER_PROJECT:-3}"
STATE_PATH="${HIVE_AUTONOMOUS_LOOP_STATE_PATH:-${HOME}/.hive/server/autonomous_loop_state.json}"
START_TS=$(date +%s)

if ! command -v curl >/dev/null 2>&1; then
  echo "error: curl is required" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required" >&2
  exit 1
fi
if ! [[ "$MAX_STEPS_PER_PROJECT" =~ ^[0-9]+$ ]] || [[ "$MAX_STEPS_PER_PROJECT" -lt 1 ]] || [[ "$MAX_STEPS_PER_PROJECT" -gt 20 ]]; then
  echo "error: HIVE_AUTONOMOUS_MAX_STEPS_PER_PROJECT must be integer in [1..20]" >&2
  exit 1
fi

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "skip: another autonomous loop tick is running (lock: $LOCK_FILE)"
    exit 0
  fi
else
  if ! mkdir "$LOCK_DIR_FALLBACK" 2>/dev/null; then
    echo "skip: another autonomous loop tick is running (lockdir: $LOCK_DIR_FALLBACK)"
    exit 0
  fi
  trap 'rmdir "$LOCK_DIR_FALLBACK" >/dev/null 2>&1 || true' EXIT
fi

PROJECT_IDS=()
if [[ -n "$PROJECT_IDS_RAW" ]]; then
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    PROJECT_IDS+=("$line")
  done < <(echo "$PROJECT_IDS_RAW" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | awk 'NF')
else
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    PROJECT_IDS+=("$line")
  done < <(curl -fsS --max-time "$TIMEOUT_SEC" "$API_BASE/projects" | jq -r '.projects[]?.id // empty')
fi

if [[ "${#PROJECT_IDS[@]}" -eq 0 ]]; then
  echo "no projects found for autonomous loop tick"
  exit 0
fi

ok=0
deferred=0
failed=0
FINALIZED=0

write_loop_state() {
  local status="$1"
  local exit_code="${2:-0}"
  local now_ts
  now_ts=$(date +%s)
  mkdir -p "$(dirname "$STATE_PATH")"
  jq -nc \
    --arg status "$status" \
    --argjson started_at "$START_TS" \
    --argjson finished_at "$now_ts" \
    --argjson updated_at "$now_ts" \
    --argjson exit_code "${exit_code:-0}" \
    --argjson ok "$ok" \
    --argjson deferred "$deferred" \
    --argjson failed "$failed" \
    --argjson projects_total "${#PROJECT_IDS[@]}" \
    --arg base_url "$BASE_URL" \
    --argjson use_run_cycle "$USE_RUN_CYCLE" \
    --argjson use_tick_all "$USE_TICK_ALL" \
    --argjson max_steps_per_project "$MAX_STEPS_PER_PROJECT" \
    '{
      started_at:$started_at,
      finished_at:$finished_at,
      updated_at:$updated_at,
      status:$status,
      exit_code:$exit_code,
      summary:{
        ok:$ok,
        deferred:$deferred,
        failed:$failed,
        projects_total:$projects_total
      },
      config:{
        base_url:$base_url,
        use_run_cycle:$use_run_cycle,
        use_tick_all:$use_tick_all,
        max_steps_per_project:$max_steps_per_project
      }
    }' > "$STATE_PATH" 2>/dev/null || true
}

on_exit() {
  local rc="$?"
  if [[ "$FINALIZED" -eq 0 ]]; then
    local status="failed"
    if [[ "$rc" -eq 0 ]]; then
      status="ok"
    fi
    write_loop_state "$status" "$rc"
  fi
}
trap on_exit EXIT

write_loop_state "running" "0"

process_row() {
  local project_id="$1"
  local action="$2"
  local error="$3"
  local reason="$4"
  local terminal="$5"
  local terminal_status="$6"
  local pr_ready="$7"

  if [[ -n "$action" ]]; then
    case "$action" in
      dispatched_next_task|advanced_with_github_checks|execution_stage_resolved|await_execution_stage_result|await_manual_stage_resolution|idle_no_todo_tasks)
        if [[ "$terminal" == "true" ]]; then
          echo "[$project_id] action=$action terminal=$terminal_status pr_ready=$pr_ready"
        else
          echo "[$project_id] action=$action"
        fi
        ok=$((ok + 1))
        ;;
      manual_evaluate_required)
        echo "[$project_id] action=$action reason=${reason:-unknown}"
        deferred=$((deferred + 1))
        ;;
      *)
        echo "[$project_id] unknown action: $action"
        failed=$((failed + 1))
        ;;
    esac
  elif [[ -n "$error" ]]; then
    echo "[$project_id] error=$error"
    failed=$((failed + 1))
  else
    echo "[$project_id] unexpected response (no action/error)"
    failed=$((failed + 1))
  fi
}

run_per_project_ticks() {
  for project_id in "${PROJECT_IDS[@]}"; do
    payload=$(jq -nc --argjson auto_start "$AUTO_START" '{auto_start:$auto_start}')
    response=$(curl -sS --max-time "$TIMEOUT_SEC" -X POST \
      -H 'Content-Type: application/json' \
      -d "$payload" \
      "$API_BASE/projects/$project_id/autonomous/loop/tick" || true)

    action=$(echo "$response" | jq -r '.action // empty' 2>/dev/null || true)
    error=$(echo "$response" | jq -r '.error // empty' 2>/dev/null || true)
    reason=$(echo "$response" | jq -r '.reason // empty' 2>/dev/null || true)
    process_row "$project_id" "$action" "$error" "$reason" "" "" ""
  done
}

run_tick_all() {
  project_ids_json=$(printf '%s\n' "${PROJECT_IDS[@]}" | jq -R . | jq -s .)
  payload=$(jq -nc \
    --argjson auto_start "$AUTO_START" \
    --argjson project_ids "$project_ids_json" \
    '{auto_start:$auto_start, project_ids:$project_ids}')
  response=$(curl -sS --max-time "$TIMEOUT_SEC" -X POST \
    -H 'Content-Type: application/json' \
    -d "$payload" \
    "$API_BASE/autonomous/loop/tick-all" || true)
  has_results=$(echo "$response" | jq -r 'has("results")' 2>/dev/null || echo "false")
  if [[ "$has_results" == "true" ]]; then
    while IFS= read -r row; do
      project_id=$(echo "$row" | jq -r '.project_id // "unknown"' 2>/dev/null || echo "unknown")
      action=$(echo "$row" | jq -r '.action // empty' 2>/dev/null || true)
      error=$(echo "$row" | jq -r '.error // empty' 2>/dev/null || true)
      reason=$(echo "$row" | jq -r '.reason // empty' 2>/dev/null || true)
      terminal=$(echo "$row" | jq -r '.terminal // empty' 2>/dev/null || true)
      terminal_status=$(echo "$row" | jq -r '.terminal_status // empty' 2>/dev/null || true)
      pr_ready=$(echo "$row" | jq -r '.pr_ready // empty' 2>/dev/null || true)
      process_row "$project_id" "$action" "$error" "$reason" "$terminal" "$terminal_status" "$pr_ready"
    done < <(echo "$response" | jq -c '.results[]' 2>/dev/null || true)
  else
    return 1
  fi
  return 0
}

run_cycle() {
  project_ids_json=$(printf '%s\n' "${PROJECT_IDS[@]}" | jq -R . | jq -s .)
  payload=$(jq -nc \
    --argjson auto_start "$AUTO_START" \
    --argjson project_ids "$project_ids_json" \
    --argjson max_steps "$MAX_STEPS_PER_PROJECT" \
    '{auto_start:$auto_start, project_ids:$project_ids, max_steps_per_project:$max_steps}')
  response=$(curl -sS --max-time "$TIMEOUT_SEC" -X POST \
    -H 'Content-Type: application/json' \
    -d "$payload" \
    "$API_BASE/autonomous/loop/run-cycle" || true)
  has_results=$(echo "$response" | jq -r 'has("results")' 2>/dev/null || echo "false")
  if [[ "$has_results" == "true" ]]; then
    while IFS= read -r row; do
      project_id=$(echo "$row" | jq -r '.project_id // "unknown"' 2>/dev/null || echo "unknown")
      action=$(echo "$row" | jq -r '.action // empty' 2>/dev/null || true)
      error=$(echo "$row" | jq -r '.error // empty' 2>/dev/null || true)
      reason=$(echo "$row" | jq -r '.reason // empty' 2>/dev/null || true)
      terminal=$(echo "$row" | jq -r '.terminal // empty' 2>/dev/null || true)
      terminal_status=$(echo "$row" | jq -r '.terminal_status // empty' 2>/dev/null || true)
      pr_ready=$(echo "$row" | jq -r '.pr_ready // empty' 2>/dev/null || true)
      process_row "$project_id" "$action" "$error" "$reason" "$terminal" "$terminal_status" "$pr_ready"
    done < <(echo "$response" | jq -c '.results[]' 2>/dev/null || true)
  else
    return 1
  fi
  return 0
}

if [[ "$USE_RUN_CYCLE" == "true" ]]; then
  if ! run_cycle; then
    echo "warn: run-cycle unavailable or invalid response; falling back to tick-all/per-project"
    if [[ "$USE_TICK_ALL" == "true" ]]; then
      if ! run_tick_all; then
        echo "warn: tick-all unavailable or invalid response; falling back to per-project tick"
        run_per_project_ticks
      fi
    else
      run_per_project_ticks
    fi
  fi
else
  if [[ "$USE_TICK_ALL" == "true" ]]; then
    if ! run_tick_all; then
      echo "warn: tick-all unavailable or invalid response; falling back to per-project tick"
      run_per_project_ticks
    fi
  else
    run_per_project_ticks
  fi
fi

echo "summary: ok=$ok deferred=$deferred failed=$failed projects=${#PROJECT_IDS[@]}"
if [[ "$failed" -gt 0 ]]; then
  FINALIZED=1
  write_loop_state "failed" "1"
  exit 1
fi
FINALIZED=1
write_loop_state "ok" "0"

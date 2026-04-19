#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="daily"
PROJECT_ID="${HIVE_ACCEPTANCE_PROJECT_ID:-default}"
BASE_URL="${HIVE_OPERATOR_BASE_URL:-http://hive-core:${HIVE_CORE_PORT:-8787}}"
PRINT_PLAN=false
OPS_SUMMARY_ONLY=false
AUTO_REMEDIATE_STALE="${HIVE_OPERATOR_AUTO_REMEDIATE_STALE:-true}"
DEEP_AUTO_REMEDIATE_STALE="${HIVE_OPERATOR_DEEP_AUTO_REMEDIATE_STALE:-false}"
REMEDIATE_ACTION="${HIVE_OPERATOR_REMEDIATE_ACTION:-escalated}"
PROJECT_HEALTH_PROFILE="${HIVE_OPERATOR_PROJECT_HEALTH_PROFILE:-prod}"
ACCEPTANCE_PRESET_OVERRIDE="${HIVE_OPERATOR_ACCEPTANCE_PRESET:-}"
ACCEPTANCE_EXTRA_ARGS_RAW="${HIVE_OPERATOR_ACCEPTANCE_EXTRA_ARGS:-}"
REMEDIATE_OVERRIDE=""
DAILY_REMEDIATE_OVERRIDE=""
DEEP_REMEDIATE_OVERRIDE=""
REMEDIATE_ACTION_OVERRIDE=""
SKIP_PREFLIGHT=false
SKIP_SELF_CHECK=false

usage() {
  cat <<'EOF'
Usage:
  ./scripts/autonomous_operator_profile.sh [--mode <daily|deep|dry-run>] [--project <id>] [--base-url <url>] [--print-plan] [--ops-summary-only] [--acceptance-preset <fast|strict|full|full-deep>] [--acceptance-extra-args "<...>"] [--remediate|--no-remediate|--no-remediation] [--daily-remediate|--no-daily-remediate] [--deep-remediate|--no-deep-remediate] [--remediate-action <escalated|failed>] [--project-health-profile <prod|strict|relaxed>] [--skip-preflight] [--skip-self-check]

Modes:
  daily    Container-first daily baseline: preflight -> stale remediation -> strict gate -> ops summary
  deep     Extended validation: preflight -> deep self-check -> [optional stale remediation] -> full-deep gate -> ops summary
  dry-run  Safe preview: print strict/full-deep acceptance env plans + current ops summary

Examples:
  ./scripts/autonomous_operator_profile.sh
  ./scripts/autonomous_operator_profile.sh --mode deep --project demo
  ./scripts/autonomous_operator_profile.sh --mode deep --project demo --remediate
  ./scripts/autonomous_operator_profile.sh --mode deep --project demo --no-deep-remediate
  ./scripts/autonomous_operator_profile.sh --mode daily --project demo --no-remediation
  ./scripts/autonomous_operator_profile.sh --mode daily --project demo --remediate-action failed
  ./scripts/autonomous_operator_profile.sh --mode daily --project demo --project-health-profile strict
  ./scripts/autonomous_operator_profile.sh --mode deep --project demo --acceptance-preset full
  ./scripts/autonomous_operator_profile.sh --mode daily --project demo --acceptance-extra-args "--summary-json --skip-telegram"
  ./scripts/autonomous_operator_profile.sh --mode daily --project demo --ops-summary-only
  ./scripts/autonomous_operator_profile.sh --mode deep --project demo --skip-preflight --skip-self-check
  ./scripts/autonomous_operator_profile.sh --mode dry-run --project demo --print-plan
EOF
}

normalize_bool() {
  local value="$1"
  case "$value" in
    true|false)
      printf '%s\n' "$value"
      ;;
    *)
      echo "error: expected boolean true|false, got: $value" >&2
      exit 2
      ;;
  esac
}

normalize_remediate_action() {
  local value="$1"
  case "$value" in
    escalated|failed)
      printf '%s\n' "$value"
      ;;
    *)
      echo "error: --remediate-action must be one of: escalated, failed" >&2
      exit 2
      ;;
  esac
}

normalize_project_health_profile() {
  local value="$1"
  case "$value" in
    prod|strict|relaxed)
      printf '%s\n' "$value"
      ;;
    *)
      echo "error: --project-health-profile must be one of: prod, strict, relaxed" >&2
      exit 2
      ;;
  esac
}

normalize_acceptance_preset() {
  local value="$1"
  case "$value" in
    fast|strict|full|full-deep)
      printf '%s\n' "$value"
      ;;
    *)
      echo "error: --acceptance-preset must be one of: fast, strict, full, full-deep" >&2
      exit 2
      ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      if [[ $# -lt 2 ]]; then
        echo "error: --mode requires value" >&2
        exit 2
      fi
      MODE="$2"
      shift 2
      ;;
    --project)
      if [[ $# -lt 2 ]]; then
        echo "error: --project requires value" >&2
        exit 2
      fi
      PROJECT_ID="$2"
      shift 2
      ;;
    --base-url)
      if [[ $# -lt 2 ]]; then
        echo "error: --base-url requires value" >&2
        exit 2
      fi
      BASE_URL="$2"
      shift 2
      ;;
    --print-plan)
      PRINT_PLAN=true
      shift
      ;;
    --ops-summary-only)
      OPS_SUMMARY_ONLY=true
      shift
      ;;
    --acceptance-preset)
      if [[ $# -lt 2 ]]; then
        echo "error: --acceptance-preset requires value" >&2
        exit 2
      fi
      ACCEPTANCE_PRESET_OVERRIDE="$2"
      shift 2
      ;;
    --acceptance-extra-args)
      if [[ $# -lt 2 ]]; then
        echo "error: --acceptance-extra-args requires value" >&2
        exit 2
      fi
      ACCEPTANCE_EXTRA_ARGS_RAW="$2"
      shift 2
      ;;
    --remediate)
      REMEDIATE_OVERRIDE="true"
      shift
      ;;
    --no-remediate|--no-remediation)
      REMEDIATE_OVERRIDE="false"
      shift
      ;;
    --daily-remediate)
      DAILY_REMEDIATE_OVERRIDE="true"
      shift
      ;;
    --no-daily-remediate)
      DAILY_REMEDIATE_OVERRIDE="false"
      shift
      ;;
    --deep-remediate)
      DEEP_REMEDIATE_OVERRIDE="true"
      shift
      ;;
    --no-deep-remediate)
      DEEP_REMEDIATE_OVERRIDE="false"
      shift
      ;;
    --remediate-action)
      if [[ $# -lt 2 ]]; then
        echo "error: --remediate-action requires value" >&2
        exit 2
      fi
      REMEDIATE_ACTION_OVERRIDE="$2"
      shift 2
      ;;
    --project-health-profile)
      if [[ $# -lt 2 ]]; then
        echo "error: --project-health-profile requires value" >&2
        exit 2
      fi
      PROJECT_HEALTH_PROFILE="$2"
      shift 2
      ;;
    --skip-preflight)
      SKIP_PREFLIGHT=true
      shift
      ;;
    --skip-self-check)
      SKIP_SELF_CHECK=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$MODE" in
  daily|deep|dry-run) ;;
  *)
    echo "error: --mode must be one of: daily, deep, dry-run" >&2
    exit 2
    ;;
esac

if [[ "$MODE" == "dry-run" ]]; then
  PRINT_PLAN=true
fi

AUTO_REMEDIATE_STALE="$(normalize_bool "$AUTO_REMEDIATE_STALE")"
DEEP_AUTO_REMEDIATE_STALE="$(normalize_bool "$DEEP_AUTO_REMEDIATE_STALE")"
if [[ -n "$REMEDIATE_OVERRIDE" ]]; then
  REMEDIATE_OVERRIDE="$(normalize_bool "$REMEDIATE_OVERRIDE")"
fi
if [[ -n "$DAILY_REMEDIATE_OVERRIDE" ]]; then
  DAILY_REMEDIATE_OVERRIDE="$(normalize_bool "$DAILY_REMEDIATE_OVERRIDE")"
fi
if [[ -n "$DEEP_REMEDIATE_OVERRIDE" ]]; then
  DEEP_REMEDIATE_OVERRIDE="$(normalize_bool "$DEEP_REMEDIATE_OVERRIDE")"
fi
REMEDIATE_ACTION="$(normalize_remediate_action "$REMEDIATE_ACTION")"
if [[ -n "$REMEDIATE_ACTION_OVERRIDE" ]]; then
  REMEDIATE_ACTION="$(normalize_remediate_action "$REMEDIATE_ACTION_OVERRIDE")"
fi
PROJECT_HEALTH_PROFILE="$(normalize_project_health_profile "$PROJECT_HEALTH_PROFILE")"
if [[ -n "$ACCEPTANCE_PRESET_OVERRIDE" ]]; then
  ACCEPTANCE_PRESET_OVERRIDE="$(normalize_acceptance_preset "$ACCEPTANCE_PRESET_OVERRIDE")"
fi

DAILY_AUTO_REMEDIATE_STALE="$AUTO_REMEDIATE_STALE"
DEEP_AUTO_REMEDIATE_STALE_EFFECTIVE="$DEEP_AUTO_REMEDIATE_STALE"
if [[ -n "$REMEDIATE_OVERRIDE" ]]; then
  DAILY_AUTO_REMEDIATE_STALE="$REMEDIATE_OVERRIDE"
  DEEP_AUTO_REMEDIATE_STALE_EFFECTIVE="$REMEDIATE_OVERRIDE"
fi
if [[ -n "$DAILY_REMEDIATE_OVERRIDE" ]]; then
  DAILY_AUTO_REMEDIATE_STALE="$DAILY_REMEDIATE_OVERRIDE"
fi
if [[ -n "$DEEP_REMEDIATE_OVERRIDE" ]]; then
  DEEP_AUTO_REMEDIATE_STALE_EFFECTIVE="$DEEP_REMEDIATE_OVERRIDE"
fi

DAILY_ACCEPTANCE_PRESET="strict"
DEEP_ACCEPTANCE_PRESET="full-deep"
if [[ -n "$ACCEPTANCE_PRESET_OVERRIDE" ]]; then
  DAILY_ACCEPTANCE_PRESET="$ACCEPTANCE_PRESET_OVERRIDE"
  DEEP_ACCEPTANCE_PRESET="$ACCEPTANCE_PRESET_OVERRIDE"
fi

ACCEPTANCE_EXTRA_ARGS=()
if [[ -n "$ACCEPTANCE_EXTRA_ARGS_RAW" ]]; then
  set -f
  # shellcheck disable=SC2206
  ACCEPTANCE_EXTRA_ARGS=($ACCEPTANCE_EXTRA_ARGS_RAW)
  set +f
fi

case "$PROJECT_HEALTH_PROFILE" in
  strict)
    HEALTH_MAX_STUCK_RUNS_DEFAULT="0"
    HEALTH_MAX_NO_PROGRESS_PROJECTS_DEFAULT="0"
    HEALTH_ALLOW_LOOP_STALE_DEFAULT="false"
    ;;
  prod)
    HEALTH_MAX_STUCK_RUNS_DEFAULT="0"
    HEALTH_MAX_NO_PROGRESS_PROJECTS_DEFAULT="1"
    HEALTH_ALLOW_LOOP_STALE_DEFAULT="true"
    ;;
  relaxed)
    HEALTH_MAX_STUCK_RUNS_DEFAULT="2"
    HEALTH_MAX_NO_PROGRESS_PROJECTS_DEFAULT="2"
    HEALTH_ALLOW_LOOP_STALE_DEFAULT="true"
    ;;
esac

HEALTH_MAX_STUCK_RUNS="${HIVE_AUTONOMOUS_HEALTH_MAX_STUCK_RUNS:-$HEALTH_MAX_STUCK_RUNS_DEFAULT}"
HEALTH_MAX_NO_PROGRESS_PROJECTS="${HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS:-$HEALTH_MAX_NO_PROGRESS_PROJECTS_DEFAULT}"
HEALTH_ALLOW_LOOP_STALE="$(normalize_bool "${HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE:-$HEALTH_ALLOW_LOOP_STALE_DEFAULT}")"

if ! [[ "$HEALTH_MAX_STUCK_RUNS" =~ ^[0-9]+$ ]]; then
  echo "error: HIVE_AUTONOMOUS_HEALTH_MAX_STUCK_RUNS must be an integer >= 0" >&2
  exit 2
fi
if ! [[ "$HEALTH_MAX_NO_PROGRESS_PROJECTS" =~ ^[0-9]+$ ]]; then
  echo "error: HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS must be an integer >= 0" >&2
  exit 2
fi

run_cmd() {
  local desc="$1"
  shift
  echo ""
  echo "== $desc =="
  echo "+ $*"
  if [[ "$PRINT_PLAN" == "true" ]]; then
    return 0
  fi
  "$@"
}

run_acceptance_gate_with_preset() {
  local preset="$1"
  local desc="$2"
  shift 2
  local cmd=("$@" ./scripts/acceptance_gate_presets.sh "$preset" --project "$PROJECT_ID")
  if [[ "${#ACCEPTANCE_EXTRA_ARGS[@]}" -gt 0 ]]; then
    cmd+=(-- "${ACCEPTANCE_EXTRA_ARGS[@]}")
  fi
  run_cmd "$desc" "${cmd[@]}"
}

run_acceptance_preset_preview() {
  local preset="$1"
  local desc="$2"
  local cmd=(./scripts/acceptance_gate_presets.sh "$preset" --project "$PROJECT_ID" --print-env-only)
  if [[ "${#ACCEPTANCE_EXTRA_ARGS[@]}" -gt 0 ]]; then
    cmd+=(-- "${ACCEPTANCE_EXTRA_ARGS[@]}")
  fi
  run_cmd "$desc" "${cmd[@]}"
}

run_preflight_if_enabled() {
  if [[ "$SKIP_PREFLIGHT" == "true" ]]; then
    echo "[skip] container preflight (--skip-preflight)"
    return 0
  fi
  run_cmd "Container preflight" ./scripts/hive_ops_preflight.sh
}

run_deep_self_check_if_enabled() {
  if [[ "$SKIP_SELF_CHECK" == "true" ]]; then
    echo "[skip] deep self-check (--skip-self-check)"
    return 0
  fi
  run_cmd "Deep self-check (preset smoke + runtime parity)" \
    ./scripts/hive_ops_run.sh ./scripts/acceptance_toolchain_self_check_deep.sh
}

echo "== Autonomous Operator Profile =="
echo "mode=$MODE"
echo "project_id=$PROJECT_ID"
echo "base_url=$BASE_URL"
echo "print_plan=$PRINT_PLAN"
echo "ops_summary_only=$OPS_SUMMARY_ONLY"
echo "daily_auto_remediate_stale=$DAILY_AUTO_REMEDIATE_STALE"
echo "deep_auto_remediate_stale=$DEEP_AUTO_REMEDIATE_STALE_EFFECTIVE"
echo "remediate_action=$REMEDIATE_ACTION"
echo "acceptance_preset_daily=$DAILY_ACCEPTANCE_PRESET"
echo "acceptance_preset_deep=$DEEP_ACCEPTANCE_PRESET"
echo "acceptance_extra_args_raw=$ACCEPTANCE_EXTRA_ARGS_RAW"
echo "acceptance_extra_args_count=${#ACCEPTANCE_EXTRA_ARGS[@]}"
echo "project_health_profile=$PROJECT_HEALTH_PROFILE"
echo "health_max_stuck_runs=$HEALTH_MAX_STUCK_RUNS"
echo "health_max_no_progress_projects=$HEALTH_MAX_NO_PROGRESS_PROJECTS"
echo "health_allow_loop_stale=$HEALTH_ALLOW_LOOP_STALE"
echo "skip_preflight=$SKIP_PREFLIGHT"
echo "skip_self_check=$SKIP_SELF_CHECK"
if [[ "$MODE" != "deep" && "$SKIP_SELF_CHECK" == "true" ]]; then
  echo "[info] --skip-self-check has no effect in mode=$MODE"
fi
if [[ "$OPS_SUMMARY_ONLY" == "true" ]]; then
  echo "[info] ops-summary-only mode: skipping preflight, deep self-check, remediation, acceptance gate"
  run_cmd "Ops summary (json)" \
    ./scripts/hive_ops_run.sh env HIVE_BASE_URL="$BASE_URL" uv run --no-project python scripts/acceptance_ops_summary.py --json
  echo ""
  echo "[ok] operator profile completed"
  exit 0
fi

case "$MODE" in
  daily)
    run_preflight_if_enabled
    if [[ "$DAILY_AUTO_REMEDIATE_STALE" == "true" ]]; then
      run_cmd "Stale runs remediation (apply before strict gate)" \
        ./scripts/hive_ops_run.sh \
          env \
            HIVE_BASE_URL="$BASE_URL" \
            HIVE_AUTONOMOUS_REMEDIATE_PROJECT_ID="$PROJECT_ID" \
            HIVE_AUTONOMOUS_REMEDIATE_ACTION="$REMEDIATE_ACTION" \
            HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=false \
            HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=true \
            ./scripts/autonomous_remediate_stale_runs.sh
    else
      echo "[skip] stale runs remediation (daily auto-remediation disabled)"
    fi
    run_acceptance_gate_with_preset \
      "$DAILY_ACCEPTANCE_PRESET" \
      "Acceptance gate (${DAILY_ACCEPTANCE_PRESET} preset, operator-safe health thresholds)" \
      env \
      HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE="$HEALTH_ALLOW_LOOP_STALE" \
      HIVE_AUTONOMOUS_HEALTH_MAX_STUCK_RUNS="$HEALTH_MAX_STUCK_RUNS" \
      HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS="$HEALTH_MAX_NO_PROGRESS_PROJECTS"
    run_cmd "Ops summary (json)" \
      ./scripts/hive_ops_run.sh env HIVE_BASE_URL="$BASE_URL" uv run --no-project python scripts/acceptance_ops_summary.py --json
    ;;
  deep)
    run_preflight_if_enabled
    run_deep_self_check_if_enabled
    if [[ "$DEEP_AUTO_REMEDIATE_STALE_EFFECTIVE" == "true" ]]; then
      run_cmd "Stale runs remediation (apply before full-deep gate)" \
        ./scripts/hive_ops_run.sh \
          env \
            HIVE_BASE_URL="$BASE_URL" \
            HIVE_AUTONOMOUS_REMEDIATE_PROJECT_ID="$PROJECT_ID" \
            HIVE_AUTONOMOUS_REMEDIATE_ACTION="$REMEDIATE_ACTION" \
            HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=false \
            HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=true \
            ./scripts/autonomous_remediate_stale_runs.sh
    else
      echo "[skip] stale runs remediation (deep auto-remediation disabled)"
    fi
    run_acceptance_gate_with_preset \
      "$DEEP_ACCEPTANCE_PRESET" \
      "Acceptance gate (${DEEP_ACCEPTANCE_PRESET} preset, operator-safe health thresholds)" \
      env \
      HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE="$HEALTH_ALLOW_LOOP_STALE" \
      HIVE_AUTONOMOUS_HEALTH_MAX_STUCK_RUNS="$HEALTH_MAX_STUCK_RUNS" \
      HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS="$HEALTH_MAX_NO_PROGRESS_PROJECTS"
    run_cmd "Ops summary (json)" \
      ./scripts/hive_ops_run.sh env HIVE_BASE_URL="$BASE_URL" uv run --no-project python scripts/acceptance_ops_summary.py --json
    ;;
  dry-run)
    if [[ -n "$ACCEPTANCE_PRESET_OVERRIDE" ]]; then
      run_acceptance_preset_preview \
        "$ACCEPTANCE_PRESET_OVERRIDE" \
        "Acceptance ${ACCEPTANCE_PRESET_OVERRIDE} preset (env preview)"
    else
      run_acceptance_preset_preview \
        strict \
        "Acceptance strict preset (env preview)"
      run_acceptance_preset_preview \
        full-deep \
        "Acceptance full-deep preset (env preview)"
    fi
    run_cmd "Ops summary (json)" \
      ./scripts/hive_ops_run.sh env HIVE_BASE_URL="$BASE_URL" uv run --no-project python scripts/acceptance_ops_summary.py --json
    ;;
esac

echo ""
echo "[ok] operator profile completed"

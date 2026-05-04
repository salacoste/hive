#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-fast}"
shift || true

PRINT_ENV_ONLY=false
PROJECT_ID_OVERRIDE=""
filtered_args=()
while [[ "$#" -gt 0 ]]; do
  arg="$1"
  shift
  if [[ "$arg" == "--print-env-only" ]]; then
    PRINT_ENV_ONLY=true
    continue
  fi
  if [[ "$arg" == "--project" ]]; then
    if [[ "$#" -eq 0 ]]; then
      echo "error: --project requires value" >&2
      exit 2
    fi
    PROJECT_ID_OVERRIDE="$1"
    shift
    continue
  fi
  filtered_args+=("$arg")
done

case "$MODE" in
  fast)
    export HIVE_ACCEPTANCE_SKIP_CHECKLIST="true"
    export HIVE_ACCEPTANCE_SKIP_TELEGRAM="true"
    export HIVE_ACCEPTANCE_ENFORCE_HISTORY=""
    export HIVE_ACCEPTANCE_SUMMARY_JSON=""
    export HIVE_ACCEPTANCE_RUN_SELF_CHECK=""
    export HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK=""
    export HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=""
    export HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=""
    export HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET="false"
    export HIVE_DELIVERY_E2E_SKIP_REAL=""
    export HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=""
    ;;
  strict)
    export HIVE_ACCEPTANCE_SKIP_CHECKLIST="true"
    export HIVE_ACCEPTANCE_SKIP_TELEGRAM=""
    export HIVE_ACCEPTANCE_ENFORCE_HISTORY="true"
    export HIVE_ACCEPTANCE_SUMMARY_JSON="true"
    export HIVE_ACCEPTANCE_RUN_SELF_CHECK=""
    export HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK=""
    export HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=""
    export HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=""
    export HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET="true"
    export HIVE_DELIVERY_E2E_SKIP_REAL=""
    export HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=""
    ;;
  full)
    export HIVE_ACCEPTANCE_SKIP_CHECKLIST="true"
    export HIVE_ACCEPTANCE_SKIP_TELEGRAM=""
    export HIVE_ACCEPTANCE_ENFORCE_HISTORY="true"
    export HIVE_ACCEPTANCE_SUMMARY_JSON="true"
    export HIVE_ACCEPTANCE_RUN_SELF_CHECK="true"
    export HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK="true"
    export HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=""
    export HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=""
    export HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET="true"
    export HIVE_DELIVERY_E2E_SKIP_REAL=""
    export HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=""
    ;;
  full-deep)
    export HIVE_ACCEPTANCE_SKIP_CHECKLIST="true"
    export HIVE_ACCEPTANCE_SKIP_TELEGRAM=""
    export HIVE_ACCEPTANCE_ENFORCE_HISTORY="true"
    export HIVE_ACCEPTANCE_SUMMARY_JSON="true"
    export HIVE_ACCEPTANCE_RUN_SELF_CHECK="true"
    export HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK="true"
    export HIVE_ACCEPTANCE_RUN_PRESET_SMOKE="true"
    export HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE="true"
    export HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET="true"
    export HIVE_DELIVERY_E2E_SKIP_REAL="true"
    export HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY="true"
    ;;
  *)
    echo "usage: $0 [fast|strict|full|full-deep] [--project <id>] [--print-env-only] [-- extra args passed to autonomous_acceptance_gate.sh]" >&2
    exit 2
    ;;
esac

if [[ -n "$PROJECT_ID_OVERRIDE" ]]; then
  export HIVE_ACCEPTANCE_PROJECT_ID="$PROJECT_ID_OVERRIDE"
fi

echo "== Acceptance Gate Preset =="
echo "mode=$MODE"
echo "HIVE_ACCEPTANCE_SKIP_CHECKLIST=${HIVE_ACCEPTANCE_SKIP_CHECKLIST:-}"
echo "HIVE_ACCEPTANCE_SKIP_TELEGRAM=${HIVE_ACCEPTANCE_SKIP_TELEGRAM:-}"
echo "HIVE_ACCEPTANCE_ENFORCE_HISTORY=${HIVE_ACCEPTANCE_ENFORCE_HISTORY:-}"
echo "HIVE_ACCEPTANCE_SUMMARY_JSON=${HIVE_ACCEPTANCE_SUMMARY_JSON:-}"
echo "HIVE_ACCEPTANCE_RUN_SELF_CHECK=${HIVE_ACCEPTANCE_RUN_SELF_CHECK:-}"
echo "HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK=${HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK:-}"
echo "HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=${HIVE_ACCEPTANCE_RUN_PRESET_SMOKE:-}"
echo "HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=${HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE:-}"
echo "HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET=${HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET:-}"
echo "HIVE_DELIVERY_E2E_SKIP_REAL=${HIVE_DELIVERY_E2E_SKIP_REAL:-}"
echo "HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=${HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY:-}"
echo "HIVE_ACCEPTANCE_PROJECT_ID=${HIVE_ACCEPTANCE_PROJECT_ID:-}"

if [[ "$PRINT_ENV_ONLY" == "true" ]]; then
  echo "[ok] print-only mode, gate execution skipped"
  exit 0
fi

if [[ "${#filtered_args[@]}" -gt 0 ]]; then
  exec ./scripts/autonomous_acceptance_gate.sh "${filtered_args[@]}"
fi
exec ./scripts/autonomous_acceptance_gate.sh

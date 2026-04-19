#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ok=0
failed=0

run_clean_preset() {
  env \
    -u HIVE_ACCEPTANCE_SKIP_CHECKLIST \
    -u HIVE_ACCEPTANCE_SKIP_TELEGRAM \
    -u HIVE_ACCEPTANCE_ENFORCE_HISTORY \
    -u HIVE_ACCEPTANCE_SUMMARY_JSON \
    -u HIVE_ACCEPTANCE_RUN_SELF_CHECK \
    -u HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK \
    -u HIVE_ACCEPTANCE_RUN_PRESET_SMOKE \
    -u HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE \
    -u HIVE_DELIVERY_E2E_SKIP_REAL \
    -u HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY \
    -u HIVE_ACCEPTANCE_PROJECT_ID \
    ./scripts/acceptance_gate_presets.sh "$@"
}

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

echo "== Acceptance Gate Presets Smoke =="
run_step "preset fast print-only" run_clean_preset fast --print-env-only
run_step "preset strict print-only" run_clean_preset strict --print-env-only
run_step "preset full print-only" run_clean_preset full --print-env-only
run_step "preset full-deep print-only" run_clean_preset full-deep --print-env-only
run_step "preset strict project override" run_clean_preset strict --project default --print-env-only

echo "== Presets smoke summary: ok=$ok failed=$failed =="
if [[ "$failed" -gt 0 ]]; then
  exit 1
fi

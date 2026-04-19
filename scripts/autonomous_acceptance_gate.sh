#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SKIP_CHECKLIST="${HIVE_ACCEPTANCE_SKIP_CHECKLIST:-false}"
SKIP_TELEGRAM="${HIVE_ACCEPTANCE_SKIP_TELEGRAM:-false}"
PROJECT_ID="${HIVE_ACCEPTANCE_PROJECT_ID:-default}"
REPORT_KEEP="${HIVE_ACCEPTANCE_REPORT_KEEP:-50}"
REPORT_PRUNE_APPLY="${HIVE_ACCEPTANCE_REPORT_PRUNE_APPLY:-false}"
DIGEST_DAYS="${HIVE_ACCEPTANCE_DIGEST_DAYS:-7}"
DIGEST_LIMIT="${HIVE_ACCEPTANCE_DIGEST_LIMIT:-20}"
DIGEST_JSON_PATH="${HIVE_ACCEPTANCE_DIGEST_JSON_PATH:-docs/ops/acceptance-reports/digest-latest.json}"
DIGEST_MD_PATH="${HIVE_ACCEPTANCE_DIGEST_MD_PATH:-docs/ops/acceptance-reports/digest-latest.md}"
ENFORCE_HISTORY="${HIVE_ACCEPTANCE_ENFORCE_HISTORY:-false}"
HISTORY_MAX_FAIL="${HIVE_ACCEPTANCE_HISTORY_MAX_FAIL:-0}"
HISTORY_MIN_PASS_RATE="${HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE:-1.0}"
SUMMARY_JSON="${HIVE_ACCEPTANCE_SUMMARY_JSON:-false}"
RUN_SELF_CHECK="${HIVE_ACCEPTANCE_RUN_SELF_CHECK:-false}"
RUN_DOCS_NAV_CHECK="${HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK:-false}"
RUN_PRESET_SMOKE="${HIVE_ACCEPTANCE_RUN_PRESET_SMOKE:-false}"
RUN_DELIVERY_E2E_SMOKE="${HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE:-false}"

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

echo "== Autonomous Acceptance Gate =="
echo "project_id=$PROJECT_ID skip_checklist=$SKIP_CHECKLIST skip_telegram=$SKIP_TELEGRAM"
echo "acceptance_reports_keep=$REPORT_KEEP prune_apply=$REPORT_PRUNE_APPLY"
echo "digest_days=$DIGEST_DAYS digest_limit=$DIGEST_LIMIT"
echo "enforce_history=$ENFORCE_HISTORY history_max_fail=$HISTORY_MAX_FAIL history_min_pass_rate=$HISTORY_MIN_PASS_RATE"
echo "summary_json=$SUMMARY_JSON"
echo "run_self_check=$RUN_SELF_CHECK"
echo "run_docs_nav_check=$RUN_DOCS_NAV_CHECK"
echo "run_preset_smoke=$RUN_PRESET_SMOKE"
echo "run_delivery_e2e_smoke=$RUN_DELIVERY_E2E_SMOKE"

if [[ "$RUN_SELF_CHECK" == "true" ]]; then
  run_step "acceptance toolchain self-check" ./scripts/acceptance_toolchain_self_check.sh
else
  echo "[skip] acceptance toolchain self-check"
fi
if [[ "$RUN_DOCS_NAV_CHECK" == "true" ]]; then
  run_step "acceptance docs navigation check" uv run python scripts/check_acceptance_docs_navigation.py
else
  echo "[skip] acceptance docs navigation check"
fi
if [[ "$RUN_PRESET_SMOKE" == "true" ]]; then
  run_step "acceptance presets smoke" ./scripts/acceptance_gate_presets_smoke.sh
else
  echo "[skip] acceptance presets smoke"
fi
if [[ "$RUN_DELIVERY_E2E_SMOKE" == "true" ]]; then
  run_step "autonomous delivery e2e smoke" \
    ./scripts/hive_ops_run.sh \
      env HIVE_DELIVERY_E2E_BASE_URL="${HIVE_DELIVERY_E2E_BASE_URL:-http://hive-core:${HIVE_CORE_PORT:-8787}}" \
      uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py
else
  echo "[skip] autonomous delivery e2e smoke"
fi

run_step "backlog validator" uv run python scripts/validate_backlog_markdown.py
run_step "backlog status summary" uv run python scripts/backlog_status.py
run_step "runbook sync check" uv run python scripts/check_runbook_sync.py
run_step "runtime parity" ./scripts/check_runtime_parity.sh
run_step "ops status health (project)" \
  env HIVE_AUTONOMOUS_HEALTH_PROJECT_ID="$PROJECT_ID" HIVE_AUTONOMOUS_HEALTH_PROFILE=prod ./scripts/autonomous_ops_health_check.sh
run_step "stale remediation dry-run (project)" \
  env HIVE_AUTONOMOUS_REMEDIATE_PROJECT_ID="$PROJECT_ID" HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=true ./scripts/autonomous_remediate_stale_runs.sh
run_step "run-cycle compact report" \
  bash -lc 'PORT="${HIVE_CORE_PORT:-8787}"; curl -fsS -X POST "http://localhost:${PORT}/api/autonomous/loop/run-cycle/report" -H "Content-Type: application/json" -d "{\"project_ids\":[\"'"$PROJECT_ID"'\"],\"auto_start\":false,\"max_steps_per_project\":1}" >/dev/null'
run_step "acceptance report artifact" uv run python scripts/acceptance_report_artifact.py
if [[ "$REPORT_PRUNE_APPLY" == "true" ]]; then
  run_step "acceptance report hygiene (apply)" \
    uv run python scripts/acceptance_report_hygiene.py --keep "$REPORT_KEEP" --yes
else
  run_step "acceptance report hygiene (preview)" \
    uv run python scripts/acceptance_report_hygiene.py --keep "$REPORT_KEEP"
fi
run_step "acceptance report digest artifact" \
  uv run python scripts/acceptance_report_digest.py \
    --days "$DIGEST_DAYS" \
    --limit "$DIGEST_LIMIT" \
    --out-json "$DIGEST_JSON_PATH" \
    --out-md "$DIGEST_MD_PATH"
if [[ "$ENFORCE_HISTORY" == "true" ]]; then
  run_step "acceptance history regression guard" \
    uv run python scripts/acceptance_report_regression_guard.py \
      --days "$DIGEST_DAYS" \
      --max-fail "$HISTORY_MAX_FAIL" \
      --min-pass-rate "$HISTORY_MIN_PASS_RATE"
else
  echo "[skip] acceptance history regression guard"
fi
if [[ "$SUMMARY_JSON" == "true" ]]; then
  run_step "acceptance ops summary (json)" uv run python scripts/acceptance_ops_summary.py --json
else
  run_step "acceptance ops summary" uv run python scripts/acceptance_ops_summary.py
fi

if [[ "$SKIP_TELEGRAM" != "true" ]]; then
  run_step "telegram bridge status" \
    bash -lc 'PORT="${HIVE_CORE_PORT:-8787}"; curl -fsS "http://localhost:${PORT}/api/telegram/bridge/status" >/dev/null'
else
  echo "[skip] telegram bridge status"
fi

if [[ "$SKIP_CHECKLIST" != "true" ]]; then
  run_step "local prod checklist" ./scripts/local_prod_checklist.sh
else
  echo "[skip] local prod checklist"
fi

echo "== Acceptance summary: ok=$ok failed=$failed =="
if [[ "$failed" -gt 0 ]]; then
  exit 1
fi

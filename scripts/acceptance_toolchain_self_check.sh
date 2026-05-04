#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_PRESET_SMOKE="${HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE:-false}"
RUN_RUNTIME_PARITY="${HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY:-false}"

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

echo "== Acceptance Toolchain Self-Check =="
echo "run_preset_smoke=$RUN_PRESET_SMOKE"
echo "run_runtime_parity=$RUN_RUNTIME_PARITY"

run_step "shell syntax" \
  bash -n \
    scripts/_cron_job_lib.sh \
    scripts/autonomous_acceptance_gate.sh \
    scripts/autonomous_operator_profile.sh \
    scripts/acceptance_deep_profile.sh \
    scripts/acceptance_weekly_maintenance.sh \
    scripts/acceptance_toolchain_self_check_deep.sh \
    scripts/acceptance_scheduler_snapshot.sh \
    scripts/install_acceptance_gate_launchd.sh \
    scripts/status_acceptance_gate_launchd.sh \
    scripts/uninstall_acceptance_gate_launchd.sh \
    scripts/install_acceptance_gate_cron.sh \
    scripts/status_acceptance_gate_cron.sh \
    scripts/uninstall_acceptance_gate_cron.sh \
    scripts/install_acceptance_weekly_launchd.sh \
    scripts/status_acceptance_weekly_launchd.sh \
    scripts/uninstall_acceptance_weekly_launchd.sh \
    scripts/install_acceptance_weekly_cron.sh \
    scripts/status_acceptance_weekly_cron.sh \
    scripts/uninstall_acceptance_weekly_cron.sh \
    scripts/install_autonomous_loop_cron.sh \
    scripts/status_autonomous_loop_cron.sh \
    scripts/uninstall_autonomous_loop_cron.sh
run_step "python syntax (scheduler daemon)" uv run python -m py_compile scripts/autonomous_scheduler_daemon.py

run_step "runbook sync check" uv run python scripts/check_runbook_sync.py
run_step "acceptance runbook sanity sync check" uv run python scripts/check_acceptance_runbook_sanity_sync.py
run_step "acceptance guardrails sync check" uv run python scripts/check_acceptance_guardrails_sync.py
run_step "acceptance guardrail marker-set sync check" uv run python scripts/check_acceptance_guardrail_marker_set_sync.py
run_step "acceptance self-check test-bundle sync check" uv run python scripts/check_acceptance_self_check_test_bundle_sync.py
run_step "backlog status consistency check" uv run python scripts/check_backlog_status_consistency.py
run_step "backlog status json contract check" uv run python scripts/check_backlog_status_json_contract.py
run_step "backlog status auto-refresh" sh -lc "uv run python scripts/backlog_status_artifact.py && uv run python scripts/backlog_status_hygiene.py --keep 50"
run_step "backlog status drift check" uv run python scripts/check_backlog_status_drift.py
run_step "acceptance gate toggles sync check" uv run python scripts/check_acceptance_gate_toggles_sync.py
run_step "acceptance docs navigation check" uv run python scripts/check_acceptance_docs_navigation.py
run_step "acceptance preset contract sync check" uv run python scripts/check_acceptance_preset_contract_sync.py
run_step "acceptance preset smoke determinism check" ./scripts/check_acceptance_preset_smoke_determinism.sh
run_step "backlog status artifacts index check" uv run python scripts/check_backlog_status_artifacts_index.py
run_step "backlog archive index check" uv run python scripts/check_backlog_archive_index.py
run_step "acceptance unit tests" uv run pytest scripts/tests/test_check_runbook_sync.py scripts/tests/test_acceptance_report_hygiene.py scripts/tests/test_acceptance_weekly_maintenance_script.py scripts/tests/test_acceptance_gate_presets.py scripts/tests/test_acceptance_gate_presets_smoke_script.py scripts/tests/test_acceptance_gate_presets_smoke_behavior.py scripts/tests/test_acceptance_ops_summary.py scripts/tests/test_acceptance_gate_result_artifact.py scripts/tests/test_check_operational_api_contracts.py scripts/tests/test_autonomous_scheduler_daemon.py scripts/tests/test_check_acceptance_docs_navigation.py scripts/tests/test_check_acceptance_gate_toggles_sync.py scripts/tests/test_check_acceptance_guardrails_sync.py scripts/tests/test_check_acceptance_guardrail_marker_set_sync.py scripts/tests/test_check_acceptance_preset_contract_sync.py scripts/tests/test_check_acceptance_preset_smoke_determinism_script.py scripts/tests/test_check_acceptance_runbook_sanity_sync.py scripts/tests/test_check_acceptance_self_check_test_bundle_sync.py scripts/tests/test_backlog_status.py scripts/tests/test_backlog_status_artifact.py scripts/tests/test_backlog_status_hygiene.py scripts/tests/test_validate_backlog_markdown.py scripts/tests/test_check_backlog_status_consistency.py scripts/tests/test_check_backlog_status_json_contract.py scripts/tests/test_check_backlog_status_drift.py scripts/tests/test_check_backlog_status_artifacts_index.py scripts/tests/test_acceptance_toolchain_self_check_script.py scripts/tests/test_acceptance_toolchain_self_check_deep_script.py scripts/tests/test_acceptance_deep_profile_script.py scripts/tests/test_check_backlog_archive_index.py -q
run_step "acceptance ops summary" uv run python scripts/acceptance_ops_summary.py
if [[ "$RUN_RUNTIME_PARITY" == "true" ]]; then
  run_step "runtime parity check" ./scripts/check_runtime_parity.sh
else
  echo "[skip] runtime parity check"
fi
run_step "acceptance scheduler snapshot" env HIVE_ACCEPTANCE_SNAPSHOT_TAIL_LINES=0 ./scripts/acceptance_scheduler_snapshot.sh
if [[ "$RUN_PRESET_SMOKE" == "true" ]]; then
  run_step "acceptance presets smoke" ./scripts/acceptance_gate_presets_smoke.sh
else
  echo "[skip] acceptance presets smoke"
fi

echo "== Self-check summary: ok=$ok failed=$failed =="
if [[ "$failed" -gt 0 ]]; then
  exit 1
fi

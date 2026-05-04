#!/usr/bin/env python3
"""Validate that self-check pytest bundle includes required acceptance test modules."""

from __future__ import annotations

from pathlib import Path

SELF_CHECK_PATH = Path("scripts/acceptance_toolchain_self_check.sh")

REQUIRED_TEST_MODULES = [
    "scripts/tests/test_check_runbook_sync.py",
    "scripts/tests/test_acceptance_gate_presets.py",
    "scripts/tests/test_acceptance_gate_presets_smoke_script.py",
    "scripts/tests/test_acceptance_gate_presets_smoke_behavior.py",
    "scripts/tests/test_acceptance_weekly_maintenance_script.py",
    "scripts/tests/test_acceptance_ops_summary.py",
    "scripts/tests/test_acceptance_gate_result_artifact.py",
    "scripts/tests/test_check_operational_api_contracts.py",
    "scripts/tests/test_autonomous_scheduler_daemon.py",
    "scripts/tests/test_check_acceptance_docs_navigation.py",
    "scripts/tests/test_check_acceptance_gate_toggles_sync.py",
    "scripts/tests/test_check_acceptance_guardrails_sync.py",
    "scripts/tests/test_check_acceptance_guardrail_marker_set_sync.py",
    "scripts/tests/test_check_acceptance_preset_contract_sync.py",
    "scripts/tests/test_check_acceptance_preset_smoke_determinism_script.py",
    "scripts/tests/test_check_acceptance_runbook_sanity_sync.py",
    "scripts/tests/test_backlog_status.py",
    "scripts/tests/test_backlog_status_artifact.py",
    "scripts/tests/test_backlog_status_hygiene.py",
    "scripts/tests/test_validate_backlog_markdown.py",
    "scripts/tests/test_check_backlog_status_consistency.py",
    "scripts/tests/test_check_backlog_status_json_contract.py",
    "scripts/tests/test_check_backlog_status_drift.py",
    "scripts/tests/test_check_backlog_status_artifacts_index.py",
    "scripts/tests/test_check_backlog_archive_index.py",
    "scripts/tests/test_acceptance_deep_profile_script.py",
]


def main() -> int:
    print("== Acceptance Self-Check Test Bundle Sync ==")
    if not SELF_CHECK_PATH.exists():
        print(f"[fail] missing file: {SELF_CHECK_PATH}")
        return 1

    text = SELF_CHECK_PATH.read_text(encoding="utf-8")
    missing = [m for m in REQUIRED_TEST_MODULES if m not in text]
    if missing:
        print(f"[fail] missing required test modules: {len(missing)}")
        for item in missing:
            print(f" - {item}")
        return 1

    for module in REQUIRED_TEST_MODULES:
        print(f"[ok] bundled: {module}")
    print("[ok] acceptance self-check test bundle is in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

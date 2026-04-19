#!/usr/bin/env python3
"""Validate runbook includes key acceptance sanity-check commands."""

from __future__ import annotations

from pathlib import Path

RUNBOOK_PATH = Path("docs/LOCAL_PROD_RUNBOOK.md")

REQUIRED_COMMAND_MARKERS = [
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_gate_toggles_sync.py",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_preset_contract_sync.py",
    "./scripts/check_acceptance_preset_smoke_determinism.sh",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_guardrails_sync.py",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_self_check_test_bundle_sync.py",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_guardrail_marker_set_sync.py",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_consistency.py",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_json_contract.py",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_drift.py",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_artifact.py",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_hygiene.py --keep 50",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_artifacts_index.py",
    "./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_archive_index.py",
    "scripts/autonomous_delivery_e2e_smoke.py",
]


def main() -> int:
    print("== Acceptance Runbook Sanity Sync Check ==")
    if not RUNBOOK_PATH.exists():
        print(f"[fail] missing runbook: {RUNBOOK_PATH}")
        return 1

    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_COMMAND_MARKERS if marker not in text]
    if missing:
        print(f"[fail] missing runbook sanity markers: {len(missing)}")
        for item in missing:
            print(f" - {item}")
        return 1

    for marker in REQUIRED_COMMAND_MARKERS:
        print(f"[ok] runbook contains: {marker}")
    print("[ok] acceptance runbook sanity commands are in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

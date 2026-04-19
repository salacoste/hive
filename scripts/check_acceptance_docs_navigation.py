#!/usr/bin/env python3
"""Validate key acceptance automation cross-links across docs."""

from __future__ import annotations

from pathlib import Path

CHECKS: list[tuple[Path, list[str]]] = [
    (Path("docs/LOCAL_PROD_RUNBOOK.md"), ["docs/ops/acceptance-automation-map.md"]),
    (Path("docs/autonomous-factory/README.md"), ["../ops/acceptance-automation-map.md"]),
    (Path("docs/autonomous-factory/04-operations-runbook.md"), ["../ops/acceptance-automation-map.md"]),
    (Path("docs/autonomous-factory/05-rollout-plan.md"), ["../ops/acceptance-automation-map.md"]),
    (
        Path("docs/ops/acceptance-automation-map.md"),
        [
            "## Quick Start",
            "./scripts/acceptance_gate_presets.sh fast",
            "./scripts/acceptance_gate_presets.sh strict",
            "./scripts/acceptance_gate_presets.sh full",
            "./scripts/acceptance_gate_presets.sh full-deep",
            "scripts/check_acceptance_gate_toggles_sync.py",
            "scripts/check_acceptance_preset_contract_sync.py",
            "scripts/check_acceptance_preset_smoke_determinism.sh",
            "scripts/check_acceptance_guardrails_sync.py",
            "scripts/check_acceptance_runbook_sanity_sync.py",
            "scripts/check_acceptance_self_check_test_bundle_sync.py",
            "scripts/check_acceptance_guardrail_marker_set_sync.py",
            "scripts/check_backlog_status_consistency.py",
            "scripts/check_backlog_status_json_contract.py",
            "scripts/check_backlog_status_drift.py",
            "scripts/check_backlog_status_artifacts_index.py",
            "uv run python scripts/backlog_status_artifact.py",
            "uv run python scripts/backlog_status_hygiene.py --keep 50",
            "scripts/check_backlog_archive_index.py",
            "HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true ./scripts/acceptance_toolchain_self_check.sh",
            "HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh",
            "HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh",
            "./scripts/acceptance_toolchain_self_check_deep.sh",
        ],
    ),
]


def main() -> int:
    print("== Acceptance Docs Navigation Check ==")
    missing: list[str] = []

    for path, needles in CHECKS:
        if not path.exists():
            missing.append(f"{path} :: file missing")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                missing.append(f"{path} :: missing ref '{needle}'")
            else:
                print(f"[ok] {path} contains '{needle}'")

    if missing:
        print(f"[fail] missing navigation refs: {len(missing)}")
        for item in missing:
            print(f" - {item}")
        return 1

    print("[ok] acceptance docs navigation is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

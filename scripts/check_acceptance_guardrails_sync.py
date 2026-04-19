#!/usr/bin/env python3
"""Ensure acceptance guardrail checkers are synced between self-check and docs map."""

from __future__ import annotations

from pathlib import Path

SELF_CHECK_PATH = Path("scripts/acceptance_toolchain_self_check.sh")
MAP_PATH = Path("docs/ops/acceptance-automation-map.md")

GUARDRAIL_SCRIPTS = [
    "scripts/check_acceptance_gate_toggles_sync.py",
    "scripts/check_acceptance_docs_navigation.py",
    "scripts/check_acceptance_preset_contract_sync.py",
    "scripts/check_acceptance_preset_smoke_determinism.sh",
    "scripts/check_acceptance_runbook_sanity_sync.py",
    "scripts/check_acceptance_self_check_test_bundle_sync.py",
    "scripts/check_backlog_status_consistency.py",
    "scripts/check_backlog_status_json_contract.py",
    "scripts/check_backlog_status_drift.py",
    "scripts/check_backlog_status_artifacts_index.py",
    "scripts/check_backlog_archive_index.py",
]


def _contains(path: Path, marker: str) -> bool:
    if not path.exists():
        return False
    return marker in path.read_text(encoding="utf-8")


def main() -> int:
    print("== Acceptance Guardrails Sync Check ==")
    missing: list[str] = []

    if not SELF_CHECK_PATH.exists():
        print(f"[fail] missing file: {SELF_CHECK_PATH}")
        return 1
    if not MAP_PATH.exists():
        print(f"[fail] missing file: {MAP_PATH}")
        return 1

    for marker in GUARDRAIL_SCRIPTS:
        in_self_check = _contains(SELF_CHECK_PATH, marker)
        in_map = _contains(MAP_PATH, marker)
        if in_self_check and in_map:
            print(f"[ok] synced marker: {marker}")
            continue
        if not in_self_check:
            missing.append(f"{SELF_CHECK_PATH} :: missing '{marker}'")
        if not in_map:
            missing.append(f"{MAP_PATH} :: missing '{marker}'")

    if missing:
        print(f"[fail] guardrails sync mismatch: {len(missing)}")
        for item in missing:
            print(f" - {item}")
        return 1

    print("[ok] acceptance guardrails are in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

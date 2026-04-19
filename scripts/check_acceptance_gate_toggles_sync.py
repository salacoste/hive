#!/usr/bin/env python3
"""Ensure acceptance gate toggles are documented in runbook."""

from __future__ import annotations

from pathlib import Path

GATE = Path("scripts/autonomous_acceptance_gate.sh")
RUNBOOK = Path("docs/LOCAL_PROD_RUNBOOK.md")

TOGGLES = [
    "HIVE_ACCEPTANCE_SKIP_CHECKLIST",
    "HIVE_ACCEPTANCE_SKIP_TELEGRAM",
    "HIVE_ACCEPTANCE_ENFORCE_HISTORY",
    "HIVE_ACCEPTANCE_SUMMARY_JSON",
    "HIVE_ACCEPTANCE_RUN_SELF_CHECK",
    "HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK",
    "HIVE_ACCEPTANCE_RUN_PRESET_SMOKE",
    "HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE",
]


def main() -> int:
    print("== Acceptance Gate Toggles Sync Check ==")
    if not GATE.exists():
        print(f"[fail] missing file: {GATE}")
        return 2
    if not RUNBOOK.exists():
        print(f"[fail] missing file: {RUNBOOK}")
        return 2

    gate_text = GATE.read_text(encoding="utf-8")
    runbook_text = RUNBOOK.read_text(encoding="utf-8")

    missing_gate: list[str] = []
    missing_runbook: list[str] = []

    for key in TOGGLES:
        in_gate = key in gate_text
        in_runbook = key in runbook_text
        if not in_gate:
            missing_gate.append(key)
        if not in_runbook:
            missing_runbook.append(key)
        if in_gate and in_runbook:
            print(f"[ok] {key}")

    if missing_gate or missing_runbook:
        print("[fail] toggle drift detected")
        if missing_gate:
            print(f"missing_in_gate={len(missing_gate)}")
            for key in missing_gate:
                print(f" - {key}")
        if missing_runbook:
            print(f"missing_in_runbook={len(missing_runbook)}")
            for key in missing_runbook:
                print(f" - {key}")
        return 1

    print("[ok] acceptance gate toggles are in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate acceptance preset contract markers across script, smoke, and docs."""

from __future__ import annotations

from pathlib import Path

CHECKS: list[tuple[Path, list[str]]] = [
    (
        Path("scripts/acceptance_gate_presets.sh"),
        [
            "fast)",
            "strict)",
            "full)",
            "full-deep)",
            "[fast|strict|full|full-deep]",
        ],
    ),
    (
        Path("scripts/acceptance_gate_presets_smoke.sh"),
        [
            'run_step "preset fast print-only"',
            'run_step "preset strict print-only"',
            'run_step "preset full print-only"',
            'run_step "preset full-deep print-only"',
        ],
    ),
    (
        Path("docs/ops/acceptance-automation-map.md"),
        [
            "./scripts/acceptance_gate_presets.sh fast",
            "./scripts/acceptance_gate_presets.sh strict",
            "./scripts/acceptance_gate_presets.sh full",
            "./scripts/acceptance_gate_presets.sh full-deep",
        ],
    ),
]


def main() -> int:
    print("== Acceptance Preset Contract Sync Check ==")
    missing: list[str] = []
    for path, needles in CHECKS:
        if not path.exists():
            missing.append(f"{path} :: file missing")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                missing.append(f"{path} :: missing '{needle}'")
            else:
                print(f"[ok] {path} contains '{needle}'")

    if missing:
        print(f"[fail] preset contract sync failed: {len(missing)}")
        for item in missing:
            print(f" - {item}")
        return 1

    print("[ok] acceptance preset contract is in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

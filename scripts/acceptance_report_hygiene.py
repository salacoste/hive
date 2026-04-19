#!/usr/bin/env python3
"""Maintain acceptance report artifacts with safe prune guardrails."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

OUT_DIR = Path("docs/ops/acceptance-reports")
PATTERN = "acceptance-report-*.json"


def build_index(files: list[Path]) -> Path:
    index_path = OUT_DIR / "INDEX.md"
    lines = [
        "# Acceptance Reports Index",
        "",
        f"Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        "",
        f"Artifacts: **{len(files)}**",
        "",
        "| Artifact |",
        "|---|",
    ]
    for p in files:
        lines.append(f"| [{p.name}]({p.name}) |")
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintain acceptance report artifacts")
    parser.add_argument("--keep", type=int, default=50, help="Keep newest N acceptance report artifacts (default: 50)")
    parser.add_argument("--yes", action="store_true", help="Confirm prune deletes")
    parser.add_argument("--max-preview", type=int, default=20, help="Max candidates to print in preview/output")
    args = parser.parse_args()

    if args.keep < 0:
        raise SystemExit("[error] --keep must be >= 0")
    if args.max_preview < 1:
        raise SystemExit("[error] --max-preview must be >= 1")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(OUT_DIR.glob(PATTERN), reverse=True)
    prune_candidates = files[args.keep :] if args.keep >= 0 else []
    deleted: list[Path] = []

    if prune_candidates and args.yes:
        for p in prune_candidates:
            p.unlink(missing_ok=True)
            deleted.append(p)
        files = sorted(OUT_DIR.glob(PATTERN), reverse=True)

    index_path = build_index(files)

    print("== Acceptance Report Hygiene ==")
    print(f"reports_total={len(files)}")
    print(f"keep={args.keep}")
    print(f"prune_candidates={len(prune_candidates)}")
    if prune_candidates:
        shown = prune_candidates[: args.max_preview]
        print(f"preview_shown={len(shown)}")
        for p in shown:
            print(f" ~ {p}")
        hidden = len(prune_candidates) - len(shown)
        if hidden > 0:
            print(f" ~ ... ({hidden} more)")

    print(f"deleted={len(deleted)}")
    if deleted:
        for p in deleted:
            print(f" - {p}")
        print("recovery_hint=restore deleted artifacts from git history/backups if needed")
    elif prune_candidates:
        print("[guardrail] dry-run preview only. Re-run with --yes to apply prune.")

    latest = OUT_DIR / "latest.json"
    print(f"latest_exists={latest.exists()}")
    print(f"index={index_path}")
    print("[ok] acceptance report hygiene completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

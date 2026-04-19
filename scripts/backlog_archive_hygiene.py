#!/usr/bin/env python3
"""Maintain backlog archive snapshots: build index and optionally prune old files."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

ARCHIVE_DIR = Path("docs/autonomous-factory/archive")
PATTERN = "backlog-done-snapshot-*.md"


def _parse_stamp(name: str) -> str:
    stem = Path(name).stem
    # backlog-done-snapshot-YYYYmmdd-HHMMSS
    parts = stem.split("-")
    if len(parts) < 5:
        return ""
    date_part = parts[-2]
    time_part = parts[-1]
    try:
        dt = datetime.strptime(f"{date_part}-{time_part}", "%Y%m%d-%H%M%S")
        return dt.isoformat(sep=" ", timespec="seconds")
    except ValueError:
        return ""


def build_index(files: list[Path]) -> Path:
    index_path = ARCHIVE_DIR / "INDEX.md"
    lines = [
        "# Backlog Archive Index",
        "",
        f"Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        "",
        f"Snapshots: **{len(files)}**",
        "",
        "| Snapshot | Timestamp |",
        "|---|---|",
    ]
    for p in files:
        ts = _parse_stamp(p.name) or "unknown"
        lines.append(f"| [{p.name}]({p.name}) | {ts} |")
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintain backlog archive snapshots")
    parser.add_argument("--prune-keep", type=int, default=0, help="Keep newest N snapshots, prune older (requires --yes)")
    parser.add_argument("--yes", action="store_true", help="Confirm prune deletes")
    parser.add_argument(
        "--max-preview",
        type=int,
        default=20,
        help="Max prune candidates to print in preview/output (default: 20)",
    )
    args = parser.parse_args()

    if args.prune_keep < 0:
        raise SystemExit("[error] --prune-keep must be >= 0")
    if args.max_preview < 1:
        raise SystemExit("[error] --max-preview must be >= 1")

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(ARCHIVE_DIR.glob(PATTERN), reverse=True)

    deleted: list[Path] = []
    prune_candidates: list[Path] = []
    if args.prune_keep > 0:
        prune_candidates = files[args.prune_keep :]
        if prune_candidates and args.yes:
            for p in prune_candidates:
                p.unlink(missing_ok=True)
                deleted.append(p)
            files = sorted(ARCHIVE_DIR.glob(PATTERN), reverse=True)

    index_path = build_index(files)

    print("== Backlog Archive Hygiene ==")
    print(f"snapshots_total={len(files)}")
    print(f"index={index_path}")
    if args.prune_keep > 0:
        print(f"prune_keep={args.prune_keep}")
        print(f"prune_candidates={len(prune_candidates)}")
        if prune_candidates:
            shown = prune_candidates[: args.max_preview]
            print(f"preview_shown={len(shown)}")
            for p in shown:
                print(f" ~ {p}")
            hidden = len(prune_candidates) - len(shown)
            if hidden > 0:
                print(f" ~ ... ({hidden} more)")
        if deleted:
            print(f"deleted={len(deleted)}")
            for p in deleted:
                print(f" - {p}")
            print("recovery_hint=restore snapshots from git history/backups if prune was accidental")
        else:
            print("deleted=0")
            if prune_candidates:
                print("[guardrail] dry-run preview only. Re-run with --yes to apply prune.")
    print("[ok] archive hygiene completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

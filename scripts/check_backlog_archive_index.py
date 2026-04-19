#!/usr/bin/env python3
"""Validate backlog archive index consistency against snapshot files."""

from __future__ import annotations

import re
from pathlib import Path

ARCHIVE_DIR = Path("docs/autonomous-factory/archive")
INDEX_PATH = ARCHIVE_DIR / "INDEX.md"
SNAPSHOT_PATTERN = "backlog-done-snapshot-*.md"
INDEX_LINK_RE = re.compile(r"\|\s+\[(?P<name>backlog-done-snapshot-[^\]]+\.md)\]\((?P=name)\)\s+\|")


def main() -> int:
    print("== Backlog Archive Index Check ==")
    if not INDEX_PATH.exists():
        print(f"[fail] missing index: {INDEX_PATH}")
        return 1

    snapshots = sorted(p.name for p in ARCHIVE_DIR.glob(SNAPSHOT_PATTERN))
    index_text = INDEX_PATH.read_text(encoding="utf-8")
    indexed_names = sorted(m.group("name") for m in INDEX_LINK_RE.finditer(index_text))

    missing_in_index = [name for name in snapshots if name not in indexed_names]
    stale_in_index = [name for name in indexed_names if name not in snapshots]

    fail = 0
    if "unknown" in index_text:
        print("[fail] index contains 'unknown' timestamp marker")
        fail += 1
    else:
        print("[ok] index has concrete timestamps")

    if missing_in_index:
        print(f"[fail] snapshots missing in index: {len(missing_in_index)}")
        for name in missing_in_index:
            print(f" - {name}")
        fail += 1
    else:
        print("[ok] all snapshots are indexed")

    if stale_in_index:
        print(f"[fail] stale index references: {len(stale_in_index)}")
        for name in stale_in_index:
            print(f" - {name}")
        fail += 1
    else:
        print("[ok] index has no stale snapshot references")

    if fail:
        print(f"[fail] backlog archive index check failed: {fail} issue group(s)")
        return 1

    print("[ok] backlog archive index is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

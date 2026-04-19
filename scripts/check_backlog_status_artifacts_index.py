#!/usr/bin/env python3
"""Validate backlog status artifacts index consistency against artifact files."""

from __future__ import annotations

import re
from pathlib import Path

ARTIFACT_DIR = Path("docs/ops/backlog-status")
INDEX_PATH = ARTIFACT_DIR / "INDEX.md"
ARTIFACT_PATTERN = "backlog-status-*.json"
INDEX_LINK_RE = re.compile(r"\|\s+\[(?P<name>backlog-status-[^\]]+\.json)\]\((?P=name)\)\s+\|")


def main() -> int:
    print("== Backlog Status Artifacts Index Check ==")
    if not INDEX_PATH.exists():
        print(f"[fail] missing index: {INDEX_PATH}")
        return 1

    artifacts = sorted(p.name for p in ARTIFACT_DIR.glob(ARTIFACT_PATTERN))
    index_text = INDEX_PATH.read_text(encoding="utf-8")
    indexed_names = sorted(m.group("name") for m in INDEX_LINK_RE.finditer(index_text))

    missing_in_index = [name for name in artifacts if name not in indexed_names]
    stale_in_index = [name for name in indexed_names if name not in artifacts]

    fail = 0
    if missing_in_index:
        print(f"[fail] artifacts missing in index: {len(missing_in_index)}")
        for name in missing_in_index:
            print(f" - {name}")
        fail += 1
    else:
        print("[ok] all backlog status artifacts are indexed")

    if stale_in_index:
        print(f"[fail] stale index references: {len(stale_in_index)}")
        for name in stale_in_index:
            print(f" - {name}")
        fail += 1
    else:
        print("[ok] index has no stale backlog status references")

    if fail:
        print(f"[fail] backlog status artifacts index check failed: {fail} issue group(s)")
        return 1

    print("[ok] backlog status artifacts index is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Create snapshot markdown of completed backlog tasks."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

BACKLOG = Path("docs/autonomous-factory/12-backlog-task-list.md")
ARCHIVE_DIR = Path("docs/autonomous-factory/archive")
TASK_RE = re.compile(r"^(?P<id>\d+)\.\s+`(?P<prio>P[0-2])`\s+(?P<title>.+)$")
STATUS_RE = re.compile(r"^- Status:\s+`(?P<status>[a-z_]+)`\s*$")


def main() -> int:
    if not BACKLOG.exists():
        print(f"[fail] backlog not found: {BACKLOG}")
        return 2

    lines = BACKLOG.read_text(encoding="utf-8").splitlines()
    rows: list[tuple[int, str, str]] = []

    i = 0
    while i < len(lines):
        m = TASK_RE.match(lines[i])
        if not m:
            i += 1
            continue
        task_id = int(m.group("id"))
        title = m.group("title").strip()
        prio = m.group("prio")
        status = "unknown"
        for j in range(i + 1, min(i + 15, len(lines))):
            sm = STATUS_RE.match(lines[j])
            if sm:
                status = sm.group("status")
                break
        if status == "done":
            rows.append((task_id, prio, title))
        i += 1

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = ARCHIVE_DIR / f"backlog-done-snapshot-{stamp}.md"

    md = [
        "# Backlog Done Snapshot",
        "",
        f"Source: `{BACKLOG}`",
        f"Generated at: `{dt.datetime.now().isoformat(timespec='seconds')}`",
        "",
        f"Completed tasks: **{len(rows)}**",
        "",
        "| ID | Priority | Title |",
        "|---:|:---:|---|",
    ]
    for task_id, prio, title in sorted(rows):
        md.append(f"| {task_id} | {prio} | {title} |")

    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"[ok] wrote archive snapshot: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

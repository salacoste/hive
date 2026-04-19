#!/usr/bin/env python3
"""Print compact status summary for autonomous backlog."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

BACKLOG = Path("docs/autonomous-factory/12-backlog-task-list.md")
TASK_RE = re.compile(r"^(?P<id>\d+)\.\s+`P(?P<p>[0-2])`\s+(?P<title>.+)$")
STATUS_RE = re.compile(r"^- Status:\s+`(?P<status>[a-z_]+)`\s*$")
FOCUS_RE = re.compile(r"^\d+\.\s+.*item\s+`?(?P<id>\d+)`?", re.IGNORECASE)


def _parse_backlog(path: Path) -> tuple[dict[int, dict[str, str]], list[int]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    tasks: dict[int, dict[str, str]] = {}

    i = 0
    while i < len(lines):
        m = TASK_RE.match(lines[i])
        if not m:
            i += 1
            continue
        tid = int(m.group("id"))
        status = "unknown"
        for j in range(i + 1, min(i + 15, len(lines))):
            sm = STATUS_RE.match(lines[j])
            if sm:
                status = sm.group("status")
                break
        tasks[tid] = {
            "priority": f"P{m.group('p')}",
            "title": m.group("title").strip(),
            "status": status,
        }
        i += 1

    focus_refs: list[int] = []
    in_focus = False
    for line in lines:
        if line.startswith("## Current Focus"):
            in_focus = True
            continue
        if in_focus and line.startswith("## "):
            break
        if not in_focus:
            continue
        fm = FOCUS_RE.match(line.strip())
        if fm:
            focus_refs.append(int(fm.group("id")))

    return tasks, focus_refs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print status summary for autonomous backlog.")
    parser.add_argument("--path", type=Path, default=BACKLOG, help=f"Path to backlog markdown (default: {BACKLOG})")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary")
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"[fail] backlog not found: {args.path}")
        return 2

    tasks, focus_refs = _parse_backlog(args.path)

    counts = Counter(v["status"] for v in tasks.values())
    in_progress = sorted([tid for tid, row in tasks.items() if row["status"] == "in_progress"])
    status_counts = {k: counts.get(k, 0) for k in ["todo", "in_progress", "blocked", "done", "unknown"]}

    if args.json:
        payload = {
            "tasks_total": len(tasks),
            "status_counts": status_counts,
            "in_progress": in_progress,
            "focus_refs": focus_refs,
            "focus_items": [
                (
                    {"id": tid, "missing": True}
                    if tid not in tasks
                    else {
                        "id": tid,
                        "priority": tasks[tid]["priority"],
                        "status": tasks[tid]["status"],
                        "title": tasks[tid]["title"],
                    }
                )
                for tid in focus_refs
            ],
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    print("== Backlog Status ==")
    print(f"tasks_total={len(tasks)}")
    print("status_counts=" + ", ".join(f"{k}:{status_counts[k]}" for k in ["todo", "in_progress", "blocked", "done", "unknown"]))
    print(f"in_progress={in_progress}")
    print(f"focus_refs={focus_refs}")

    if focus_refs:
        print("focus_items:")
        for tid in focus_refs:
            row = tasks.get(tid)
            if row is None:
                print(f" - {tid}: <missing>")
                continue
            print(f" - {tid}: [{row['priority']}] {row['status']} :: {row['title']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

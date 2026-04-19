#!/usr/bin/env python3
"""Validate Hive backlog markdown structure and task status consistency."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

TASK_RE = re.compile(r"^(?P<id>\d+)\.\s+`P[0-2]`\s+")
STATUS_RE = re.compile(r"^- Status:\s+`(?P<status>[a-z_]+)`\s*$")
FOCUS_ITEM_RE = re.compile(r"^\d+\.\s+.*item\s+`?(?P<id>\d+)`?", re.IGNORECASE)

ALLOWED = {"todo", "in_progress", "blocked", "done"}


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/autonomous-factory/12-backlog-task-list.md")
    if not path.exists():
        print(f"[fail] backlog file not found: {path}")
        return 2

    lines = path.read_text(encoding="utf-8").splitlines()

    tasks: dict[int, str] = {}
    in_progress: list[int] = []
    errors: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        m = TASK_RE.match(line)
        if not m:
            i += 1
            continue

        tid = int(m.group("id"))
        if tid in tasks:
            errors.append(f"duplicate task id: {tid}")

        status: str | None = None
        for j in range(i + 1, min(i + 15, len(lines))):
            sm = STATUS_RE.match(lines[j])
            if sm:
                status = sm.group("status")
                break
        if status is None:
            errors.append(f"task {tid}: missing '- Status: `...`' line")
        elif status not in ALLOWED:
            errors.append(f"task {tid}: invalid status '{status}'")
        else:
            tasks[tid] = status
            if status == "in_progress":
                in_progress.append(tid)
        i += 1

    if tasks:
        ordered = sorted(tasks)
        if ordered != list(range(min(ordered), max(ordered) + 1)):
            errors.append("task ids are not contiguous")

    if len(in_progress) > 1:
        errors.append(f"more than one in_progress task: {in_progress}")

    in_focus = False
    focus_refs: list[int] = []
    for line in lines:
        if line.startswith("## Current Focus"):
            in_focus = True
            continue
        if in_focus and line.startswith("## "):
            break
        if in_focus:
            fm = FOCUS_ITEM_RE.match(line.strip())
            if fm:
                focus_refs.append(int(fm.group("id")))

    for ref in focus_refs:
        if ref not in tasks:
            errors.append(f"Current Focus references unknown task id: {ref}")

    done_total = sum(1 for status in tasks.values() if status == "done")
    is_terminal_completion = bool(tasks) and done_total == len(tasks)

    require_focus = os.environ.get("HIVE_BACKLOG_REQUIRE_FOCUS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    require_in_progress = os.environ.get("HIVE_BACKLOG_REQUIRE_IN_PROGRESS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    # Terminal completion mode: all backlog items are done.
    # In that state we allow empty Current Focus and no in_progress task.
    if require_focus and not focus_refs and not is_terminal_completion:
        errors.append("Current Focus must reference at least one task id")
    if require_in_progress and not in_progress and not is_terminal_completion:
        errors.append("at least one task must be in_progress")
    if in_progress and focus_refs and not any(tid in focus_refs for tid in in_progress):
        errors.append(f"in_progress task(s) {in_progress} are not referenced from Current Focus {focus_refs}")

    if errors:
        print(f"[fail] backlog validation failed ({len(errors)} error(s))")
        for err in errors:
            print(f" - {err}")
        return 1

    print("[ok] backlog validation passed")
    print(f"tasks_total={len(tasks)} in_progress={in_progress or []} focus_refs={focus_refs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate parser-level consistency between backlog status and validator logic."""

from __future__ import annotations

from pathlib import Path
import re

BACKLOG_PATH = Path("docs/autonomous-factory/12-backlog-task-list.md")

STATUS_TASK_RE = re.compile(r"^(?P<id>\d+)\.\s+`P(?P<p>[0-2])`\s+(?P<title>.+)$")
STATUS_LINE_RE = re.compile(r"^- Status:\s+`(?P<status>[a-z_]+)`\s*$")
STATUS_FOCUS_RE = re.compile(r"^\d+\.\s+.*item\s+`?(?P<id>\d+)`?", re.IGNORECASE)

VALIDATOR_TASK_RE = re.compile(r"^(?P<id>\d+)\.\s+`P[0-2]`\s+")
VALIDATOR_STATUS_RE = re.compile(r"^- Status:\s+`(?P<status>[a-z_]+)`\s*$")
VALIDATOR_FOCUS_RE = re.compile(r"^\d+\.\s+.*item\s+`?(?P<id>\d+)`?", re.IGNORECASE)
VALIDATOR_ALLOWED = {"todo", "in_progress", "blocked", "done"}


def _parse_with_status_logic(lines: list[str]) -> tuple[set[int], list[int], list[int], int]:
    task_ids: set[int] = set()
    in_progress: list[int] = []

    i = 0
    while i < len(lines):
        m = STATUS_TASK_RE.match(lines[i])
        if not m:
            i += 1
            continue
        tid = int(m.group("id"))
        task_ids.add(tid)
        status = "unknown"
        for j in range(i + 1, min(i + 15, len(lines))):
            sm = STATUS_LINE_RE.match(lines[j])
            if sm:
                status = sm.group("status")
                break
        if status == "in_progress":
            in_progress.append(tid)
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
        fm = STATUS_FOCUS_RE.match(line.strip())
        if fm:
            focus_refs.append(int(fm.group("id")))

    unknown_count = 0
    i = 0
    while i < len(lines):
        m = STATUS_TASK_RE.match(lines[i])
        if not m:
            i += 1
            continue
        status = "unknown"
        for j in range(i + 1, min(i + 15, len(lines))):
            sm = STATUS_LINE_RE.match(lines[j])
            if sm:
                status = sm.group("status")
                break
        if status == "unknown":
            unknown_count += 1
        i += 1

    return task_ids, sorted(in_progress), focus_refs, unknown_count


def _parse_with_validator_logic(lines: list[str]) -> tuple[set[int], list[int], list[int]]:
    task_ids: set[int] = set()
    in_progress: list[int] = []

    i = 0
    while i < len(lines):
        m = VALIDATOR_TASK_RE.match(lines[i])
        if not m:
            i += 1
            continue

        tid = int(m.group("id"))
        task_ids.add(tid)
        status: str | None = None
        for j in range(i + 1, min(i + 15, len(lines))):
            sm = VALIDATOR_STATUS_RE.match(lines[j])
            if sm:
                status = sm.group("status")
                break
        if status in VALIDATOR_ALLOWED and status == "in_progress":
            in_progress.append(tid)
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
        fm = VALIDATOR_FOCUS_RE.match(line.strip())
        if fm:
            focus_refs.append(int(fm.group("id")))

    return task_ids, sorted(in_progress), focus_refs


def main() -> int:
    print("== Backlog Status Consistency Check ==")
    if not BACKLOG_PATH.exists():
        print(f"[fail] backlog not found: {BACKLOG_PATH}")
        return 1

    lines = BACKLOG_PATH.read_text(encoding="utf-8").splitlines()
    status_task_ids, status_in_progress, status_focus_refs, unknown_count = _parse_with_status_logic(lines)
    validator_task_ids, validator_in_progress, validator_focus_refs = _parse_with_validator_logic(lines)

    failed = False

    if status_task_ids != validator_task_ids:
        failed = True
        print("[fail] task id sets diverged between backlog_status and validator parser")
        print(f" - backlog_status only: {sorted(status_task_ids - validator_task_ids)}")
        print(f" - validator only: {sorted(validator_task_ids - status_task_ids)}")
    else:
        print(f"[ok] task id sets in sync ({len(status_task_ids)} tasks)")

    if status_in_progress != validator_in_progress:
        failed = True
        print("[fail] in_progress sets diverged between parsers")
        print(f" - backlog_status: {status_in_progress}")
        print(f" - validator: {validator_in_progress}")
    else:
        print(f"[ok] in_progress in sync: {status_in_progress}")

    if status_focus_refs != validator_focus_refs:
        failed = True
        print("[fail] Current Focus refs diverged between parsers")
        print(f" - backlog_status: {status_focus_refs}")
        print(f" - validator: {validator_focus_refs}")
    else:
        print(f"[ok] focus refs in sync: {status_focus_refs}")

    if unknown_count > 0:
        failed = True
        print(f"[fail] backlog_status parser found tasks with unknown status: {unknown_count}")
    else:
        print("[ok] backlog_status parser found no unknown statuses")

    if failed:
        print("[fail] backlog status consistency check failed")
        return 1
    print("[ok] backlog status parser and validator parser are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

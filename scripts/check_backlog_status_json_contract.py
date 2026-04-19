#!/usr/bin/env python3
"""Validate machine-readable contract for backlog_status.py --json output."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

BACKLOG_STATUS_SCRIPT = Path("scripts/backlog_status.py")
REQUIRED_TOP_LEVEL_KEYS = {"tasks_total", "status_counts", "in_progress", "focus_refs", "focus_items"}
REQUIRED_STATUS_KEYS = {"todo", "in_progress", "blocked", "done", "unknown"}


def _validate_payload(payload: dict) -> list[str]:
    errors: list[str] = []

    if set(payload.keys()) != REQUIRED_TOP_LEVEL_KEYS:
        missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(payload.keys()))
        extra = sorted(set(payload.keys()) - REQUIRED_TOP_LEVEL_KEYS)
        if missing:
            errors.append(f"missing top-level keys: {missing}")
        if extra:
            errors.append(f"unexpected top-level keys: {extra}")

    tasks_total = payload.get("tasks_total")
    if not isinstance(tasks_total, int) or tasks_total < 0:
        errors.append("tasks_total must be a non-negative integer")

    status_counts = payload.get("status_counts")
    if not isinstance(status_counts, dict):
        errors.append("status_counts must be an object")
    else:
        missing_status = sorted(REQUIRED_STATUS_KEYS - set(status_counts.keys()))
        extra_status = sorted(set(status_counts.keys()) - REQUIRED_STATUS_KEYS)
        if missing_status:
            errors.append(f"missing status_counts keys: {missing_status}")
        if extra_status:
            errors.append(f"unexpected status_counts keys: {extra_status}")
        for key in REQUIRED_STATUS_KEYS & set(status_counts.keys()):
            value = status_counts[key]
            if not isinstance(value, int) or value < 0:
                errors.append(f"status_counts.{key} must be a non-negative integer")
        if isinstance(tasks_total, int):
            total = sum(status_counts.get(key, 0) for key in REQUIRED_STATUS_KEYS)
            if total != tasks_total:
                errors.append(f"sum(status_counts)={total} does not match tasks_total={tasks_total}")

    in_progress = payload.get("in_progress")
    if not isinstance(in_progress, list) or not all(isinstance(x, int) and x > 0 for x in in_progress):
        errors.append("in_progress must be a list of positive integers")

    focus_refs = payload.get("focus_refs")
    if not isinstance(focus_refs, list) or not all(isinstance(x, int) and x > 0 for x in focus_refs):
        errors.append("focus_refs must be a list of positive integers")

    focus_items = payload.get("focus_items")
    if not isinstance(focus_items, list):
        errors.append("focus_items must be a list")
    elif isinstance(focus_refs, list) and len(focus_items) != len(focus_refs):
        errors.append("focus_items length must match focus_refs length")
    elif isinstance(focus_refs, list):
        for idx, item in enumerate(focus_items):
            if not isinstance(item, dict):
                errors.append(f"focus_items[{idx}] must be an object")
                continue
            if "id" not in item or not isinstance(item["id"], int):
                errors.append(f"focus_items[{idx}].id must be an integer")
                continue
            if item["id"] != focus_refs[idx]:
                errors.append(f"focus_items[{idx}].id must match focus_refs[{idx}]")
            if item.get("missing") is True:
                continue
            required_item_keys = {"id", "priority", "status", "title"}
            if set(item.keys()) != required_item_keys:
                errors.append(f"focus_items[{idx}] keys must be exactly {sorted(required_item_keys)} for resolved item")
                continue
            if not isinstance(item["priority"], str):
                errors.append(f"focus_items[{idx}].priority must be a string")
            if not isinstance(item["status"], str):
                errors.append(f"focus_items[{idx}].status must be a string")
            if not isinstance(item["title"], str):
                errors.append(f"focus_items[{idx}].title must be a string")

    return errors


def main() -> int:
    print("== Backlog Status JSON Contract Check ==")
    if not BACKLOG_STATUS_SCRIPT.exists():
        print(f"[fail] missing script: {BACKLOG_STATUS_SCRIPT}")
        return 1

    result = subprocess.run(
        [sys.executable, str(BACKLOG_STATUS_SCRIPT), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[fail] backlog_status --json failed with code {result.returncode}")
        if result.stderr.strip():
            print(result.stderr.strip())
        if result.stdout.strip():
            print(result.stdout.strip())
        return 1

    stdout = result.stdout.strip()
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        print(f"[fail] invalid JSON output: {exc}")
        print(stdout)
        return 1

    if not isinstance(payload, dict):
        print("[fail] JSON payload must be an object")
        return 1

    errors = _validate_payload(payload)
    if errors:
        print(f"[fail] backlog status JSON contract failed: {len(errors)}")
        for err in errors:
            print(f" - {err}")
        return 1

    print("[ok] backlog status JSON contract is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

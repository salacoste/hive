#!/usr/bin/env python3
"""Check drift between live backlog status and latest backlog status artifact."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

VALIDATOR_SCRIPT = Path("scripts/validate_backlog_markdown.py")
BACKLOG_STATUS_SCRIPT = Path("scripts/backlog_status.py")
BACKLOG_STATUS_LATEST = Path("docs/ops/backlog-status/latest.json")


def _run_backlog_validator() -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _run_backlog_status_json() -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(BACKLOG_STATUS_SCRIPT), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"backlog_status --json failed with code {result.returncode}")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("backlog_status --json returned non-object payload")
    return payload


def _read_latest_artifact_status() -> dict[str, Any]:
    if not BACKLOG_STATUS_LATEST.exists():
        raise RuntimeError(f"missing backlog status artifact: {BACKLOG_STATUS_LATEST}")
    payload = json.loads(BACKLOG_STATUS_LATEST.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("backlog status latest artifact is not an object")
    status = payload.get("status")
    if not isinstance(status, dict):
        raise RuntimeError("backlog status latest artifact missing 'status' object")
    return status


def _subset_for_compare(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "tasks_total": payload.get("tasks_total"),
        "status_counts": payload.get("status_counts"),
        "in_progress": payload.get("in_progress"),
        "focus_refs": payload.get("focus_refs"),
    }


def main() -> int:
    print("== Backlog Status Drift Check ==")
    if not VALIDATOR_SCRIPT.exists():
        print(f"[fail] missing script: {VALIDATOR_SCRIPT}")
        return 1
    if not BACKLOG_STATUS_SCRIPT.exists():
        print(f"[fail] missing script: {BACKLOG_STATUS_SCRIPT}")
        return 1

    rc, output = _run_backlog_validator()
    if rc != 0:
        print("[fail] backlog markdown validator failed")
        print(output.strip())
        return 1
    print("[ok] backlog markdown validator passed")

    try:
        live = _run_backlog_status_json()
        artifact = _read_latest_artifact_status()
    except Exception as exc:
        print(f"[fail] cannot load backlog status sources: {exc}")
        return 1

    live_cmp = _subset_for_compare(live)
    artifact_cmp = _subset_for_compare(artifact)
    if live_cmp != artifact_cmp:
        print("[fail] drift detected between live backlog status and latest artifact")
        print(f" - live: {json.dumps(live_cmp, ensure_ascii=False)}")
        print(f" - artifact: {json.dumps(artifact_cmp, ensure_ascii=False)}")
        return 1

    print("[ok] no drift between live backlog status and latest artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

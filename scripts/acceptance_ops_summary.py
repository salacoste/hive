#!/usr/bin/env python3
"""Print compact operational summary for acceptance maintenance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPORTS_DIR = Path("docs/ops/acceptance-reports")
LATEST_ARTIFACT = REPORTS_DIR / "latest.json"
DIGEST_JSON = REPORTS_DIR / "digest-latest.json"
BACKLOG_STATUS_DIR = Path("docs/ops/backlog-status")
BACKLOG_STATUS_LATEST = BACKLOG_STATUS_DIR / "latest.json"
BACKLOG_STATUS_PATTERN = "backlog-status-*.json"
BACKLOG_STATUS_SCRIPT = Path("scripts/backlog_status.py")
BACKLOG_COMPARE_KEYS = ("tasks_total", "status_counts", "in_progress", "focus_refs")
ACCEPTANCE_GATE_LAUNCHD_STATUS_SCRIPT = Path("scripts/status_acceptance_gate_launchd.sh")
ACCEPTANCE_GATE_CRON_STATUS_SCRIPT = Path("scripts/status_acceptance_gate_cron.sh")
ACCEPTANCE_WEEKLY_LAUNCHD_STATUS_SCRIPT = Path("scripts/status_acceptance_weekly_launchd.sh")
ACCEPTANCE_WEEKLY_CRON_STATUS_SCRIPT = Path("scripts/status_acceptance_weekly_cron.sh")
AUTONOMOUS_LOOP_LAUNCHD_STATUS_SCRIPT = Path("scripts/status_autonomous_loop_launchd.sh")
AUTONOMOUS_LOOP_CRON_STATUS_SCRIPT = Path("scripts/status_autonomous_loop_cron.sh")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _run_backlog_status_json() -> dict[str, Any] | None:
    if not BACKLOG_STATUS_SCRIPT.exists():
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(BACKLOG_STATUS_SCRIPT), "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _drift_signal(artifact_status: dict[str, Any], live_status: dict[str, Any] | None) -> tuple[bool | None, str | None]:
    if not artifact_status:
        return None, "missing_latest_artifact_status"
    if live_status is None:
        return None, "live_backlog_status_unavailable"

    artifact_cmp = {k: artifact_status.get(k) for k in BACKLOG_COMPARE_KEYS}
    live_cmp = {k: live_status.get(k) for k in BACKLOG_COMPARE_KEYS}
    if artifact_cmp != live_cmp:
        return True, "live_vs_artifact_mismatch"
    return False, "in_sync"


def _scheduler_status(script_path: Path) -> str | None:
    if not script_path.exists():
        return None
    try:
        result = subprocess.run(
            [str(script_path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    line = (result.stdout or "").splitlines()
    if not line:
        return None
    head = line[0].strip()
    if not head:
        return None
    if head == "not-installed":
        return "not-installed"
    if head.startswith("not-supported:"):
        return "not-supported"
    if head.startswith("error:"):
        return "error"
    return "installed"


def _docker_scheduler_status() -> str:
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--status", "running", "hive-scheduler", "-q"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown-cli-unavailable"
    if result.returncode != 0:
        return "unknown-compose-error"
    return "running" if (result.stdout or "").strip() else "not-running"


def main() -> int:
    parser = argparse.ArgumentParser(description="Acceptance ops compact summary")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    args = parser.parse_args()

    latest = _read_json(LATEST_ARTIFACT) or {}
    digest = _read_json(DIGEST_JSON) or {}
    backlog_status_doc = _read_json(BACKLOG_STATUS_LATEST) or {}
    backlog_status = backlog_status_doc.get("status") or {}
    backlog_status_counts = backlog_status.get("status_counts") or {}
    live_backlog_status = _run_backlog_status_json()
    backlog_drift_detected, backlog_drift_reason = _drift_signal(backlog_status, live_backlog_status)
    acceptance_gate_launchd = _scheduler_status(ACCEPTANCE_GATE_LAUNCHD_STATUS_SCRIPT)
    acceptance_gate_cron = _scheduler_status(ACCEPTANCE_GATE_CRON_STATUS_SCRIPT)
    acceptance_weekly_launchd = _scheduler_status(ACCEPTANCE_WEEKLY_LAUNCHD_STATUS_SCRIPT)
    acceptance_weekly_cron = _scheduler_status(ACCEPTANCE_WEEKLY_CRON_STATUS_SCRIPT)
    autonomous_loop_launchd = _scheduler_status(AUTONOMOUS_LOOP_LAUNCHD_STATUS_SCRIPT)
    autonomous_loop_cron = _scheduler_status(AUTONOMOUS_LOOP_CRON_STATUS_SCRIPT)
    docker_scheduler = _docker_scheduler_status()

    health = latest.get("health") or {}
    ops = latest.get("ops") or {}
    tg = latest.get("telegram_bridge") or {}

    summary = {
        "latest_artifact_exists": LATEST_ARTIFACT.exists(),
        "digest_exists": DIGEST_JSON.exists(),
        "latest_generated_at": latest.get("generated_at"),
        "health_status": health.get("status"),
        "ops_status": ops.get("status"),
        "telegram_status": tg.get("status"),
        "stuck_runs_total": ops.get("stuck_runs_total"),
        "no_progress_projects_total": ops.get("no_progress_projects_total"),
        "digest_window_days": digest.get("window_days"),
        "digest_artifacts_total": digest.get("artifacts_total"),
        "digest_pass": digest.get("pass"),
        "digest_fail": digest.get("fail"),
        "backlog_status_latest_exists": BACKLOG_STATUS_LATEST.exists(),
        "backlog_status_artifacts_total": len(list(BACKLOG_STATUS_DIR.glob(BACKLOG_STATUS_PATTERN))),
        "backlog_tasks_total": backlog_status.get("tasks_total"),
        "backlog_in_progress_total": len(backlog_status.get("in_progress") or []),
        "backlog_focus_refs_total": len(backlog_status.get("focus_refs") or []),
        "backlog_done_total": backlog_status_counts.get("done"),
        "backlog_todo_total": backlog_status_counts.get("todo"),
        "backlog_drift_detected": backlog_drift_detected,
        "backlog_drift_reason": backlog_drift_reason,
        "scheduler_acceptance_gate_launchd": acceptance_gate_launchd,
        "scheduler_acceptance_gate_cron": acceptance_gate_cron,
        "scheduler_acceptance_weekly_launchd": acceptance_weekly_launchd,
        "scheduler_acceptance_weekly_cron": acceptance_weekly_cron,
        "scheduler_autonomous_loop_launchd": autonomous_loop_launchd,
        "scheduler_autonomous_loop_cron": autonomous_loop_cron,
        "scheduler_hive_scheduler_container": docker_scheduler,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=True, indent=2))
        return 0

    print("== Acceptance Ops Summary ==")
    for k, v in summary.items():
        print(f"{k}={v}")
    if summary["latest_artifact_exists"] and summary["digest_exists"]:
        print("[ok] summary available")
    else:
        print("[warn] summary incomplete: run acceptance gate or weekly maintenance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

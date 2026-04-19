#!/usr/bin/env python3
"""Generate Telegram-first operator sign-off artifact (container-first)."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    timeout: int,
) -> tuple[int, dict[str, Any]]:
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        method=method.upper(),
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            status = int(resp.status)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        status = int(exc.code)
    except Exception as exc:
        return 599, {"error": f"request failed: {exc}"}
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return status, {"raw": raw}
    if isinstance(data, dict):
        return status, data
    return status, {"data": data}


def _check_bridge_status(payload: dict[str, Any]) -> tuple[bool, str]:
    bridge = payload.get("bridge") if isinstance(payload.get("bridge"), dict) else {}
    enabled = bool(bridge.get("enabled"))
    owner = bool(bridge.get("poller_owner"))
    running = bool(bridge.get("running"))
    startup = str(bridge.get("startup_status") or "").strip()
    ok = enabled and owner and running and startup == "running"
    detail = (
        f"enabled={str(enabled).lower()} "
        f"poller_owner={str(owner).lower()} "
        f"running={str(running).lower()} "
        f"startup_status={startup or '--'}"
    )
    return ok, detail


def _check_health_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    status = str(payload.get("status") or "").strip().lower()
    bridge = payload.get("telegram_bridge") if isinstance(payload.get("telegram_bridge"), dict) else {}
    running = bool(bridge.get("running"))
    startup = str(bridge.get("startup_status") or "").strip()
    ok = status == "ok" and running and startup == "running"
    detail = f"status={status or '--'} telegram_running={str(running).lower()} startup_status={startup or '--'}"
    return ok, detail


def _check_ops_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    status = str(payload.get("status") or "").strip().lower()
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    projects = payload.get("projects")
    include_runs = bool(summary.get("include_runs"))
    projects_total = int(summary.get("projects_total") or 0)
    runs_total = int(summary.get("runs_total") or 0)
    shape_ok = isinstance(projects, dict)
    ok = status == "ok" and include_runs and shape_ok
    detail = (
        f"status={status or '--'} include_runs={str(include_runs).lower()} "
        f"projects_total={projects_total} runs_total={runs_total}"
    )
    return ok, detail


def _derive_overall_status(*, machine_ok: bool, manual_status: str) -> str:
    manual = (manual_status or "pending").strip().lower()
    if manual == "fail":
        return "fail"
    if not machine_ok:
        return "fail"
    if manual == "pass":
        return "pass"
    return "pending"


def _render_markdown(report: dict[str, Any]) -> str:
    now = str(report.get("generated_at") or "")
    operator = str(report.get("operator") or "unknown")
    scenario = str(report.get("scenario") or "both")
    project_id = str(report.get("project_id") or "")
    overall = str(report.get("overall_status") or "pending")
    manual = str(report.get("manual_status") or "pending")
    machine_ok = bool(report.get("machine_ok"))
    machine_checks = report.get("machine_checks") if isinstance(report.get("machine_checks"), list) else []
    manual_checklist = report.get("manual_checklist") if isinstance(report.get("manual_checklist"), list) else []

    lines = [
        "# Telegram Operator Sign-off",
        "",
        f"- generated_at: `{now}`",
        f"- operator: `{operator}`",
        f"- scenario: `{scenario}`",
        f"- project_id: `{project_id or '--'}`",
        f"- overall_status: `{overall}`",
        f"- manual_status: `{manual}`",
        f"- machine_ok: `{str(machine_ok).lower()}`",
        "",
        "## Machine Checks",
    ]
    for check in machine_checks:
        name = str(check.get("name") or "check")
        ok = bool(check.get("ok"))
        detail = str(check.get("detail") or "")
        lines.append(f"- {'✅' if ok else '❌'} `{name}`: {detail}")
    lines.extend(
        [
            "",
            "## Manual Checklist",
            "Run from Telegram and set manual_status=pass only after confirmation.",
        ]
    )
    for row in manual_checklist:
        step = str(row.get("step") or "")
        expectation = str(row.get("expectation") or "")
        lines.append(f"- [ ] {step}: {expectation}")
    notes = str(report.get("notes") or "").strip()
    if notes:
        lines.extend(["", "## Notes", notes])
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Telegram-first operator sign-off artifact")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("HIVE_BASE_URL", f"http://localhost:{os.environ.get('HIVE_CORE_PORT', '8787')}"),
        help="Hive base URL",
    )
    parser.add_argument(
        "--project-id",
        default=os.environ.get("HIVE_ACCEPTANCE_PROJECT_ID", "default"),
        help="Project id used for ops status and checklist context",
    )
    parser.add_argument("--operator", default=os.environ.get("HIVE_OPERATOR", "unknown"), help="Operator name")
    parser.add_argument(
        "--scenario",
        choices=("existing_repo", "new_repo", "both"),
        default="both",
        help="Manual scenario scope for sign-off",
    )
    parser.add_argument(
        "--manual-status",
        choices=("pending", "pass", "fail"),
        default="pending",
        help="Manual execution status",
    )
    parser.add_argument("--notes", default="", help="Optional notes for report")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds")
    parser.add_argument(
        "--out-json",
        default="docs/ops/telegram-signoff/latest.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--out-md",
        default="docs/ops/telegram-signoff/latest.md",
        help="Output Markdown path",
    )
    args = parser.parse_args(argv)

    base = args.base_url.rstrip("/")
    checks: list[dict[str, Any]] = []

    bridge_status, bridge_payload = _request_json(
        method="GET",
        url=f"{base}/api/telegram/bridge/status",
        payload=None,
        timeout=args.timeout,
    )
    bridge_ok, bridge_detail = _check_bridge_status(bridge_payload) if bridge_status < 400 else (False, f"http={bridge_status}")
    checks.append({"name": "telegram_bridge_status", "ok": bridge_ok, "detail": bridge_detail, "http_status": bridge_status})

    health_status, health_payload = _request_json(
        method="GET",
        url=f"{base}/api/health",
        payload=None,
        timeout=args.timeout,
    )
    health_ok, health_detail = _check_health_payload(health_payload) if health_status < 400 else (False, f"http={health_status}")
    checks.append({"name": "health_telegram_snapshot", "ok": health_ok, "detail": health_detail, "http_status": health_status})

    ops_status, ops_payload = _request_json(
        method="GET",
        url=f"{base}/api/autonomous/ops/status?{urllib.parse.urlencode({'project_id': args.project_id, 'include_runs': 'true'})}",
        payload=None,
        timeout=args.timeout,
    )
    ops_ok, ops_detail = _check_ops_payload(ops_payload) if ops_status < 400 else (False, f"http={ops_status}")
    checks.append({"name": "autonomous_ops_status", "ok": ops_ok, "detail": ops_detail, "http_status": ops_status})

    remediate_status, remediate_payload = _request_json(
        method="POST",
        url=f"{base}/api/autonomous/ops/remediate-stale",
        payload={
            "project_id": args.project_id,
            "older_than_seconds": 1800,
            "max_runs": 100,
            "dry_run": True,
            "confirm": False,
            "action": "escalated",
            "reason": "telegram_operator_signoff",
        },
        timeout=args.timeout,
    )
    rem_ok = remediate_status < 400 and str(remediate_payload.get("status") or "").strip().lower() == "ok"
    rem_detail = (
        f"status={str(remediate_payload.get('status') or '--')} "
        f"candidates_total={int(remediate_payload.get('candidates_total') or 0)} "
        f"selected_total={int(remediate_payload.get('selected_total') or 0)}"
        if remediate_status < 400
        else f"http={remediate_status}"
    )
    checks.append({"name": "remediate_stale_dry_run", "ok": rem_ok, "detail": rem_detail, "http_status": remediate_status})

    machine_ok = all(bool(c.get("ok")) for c in checks)
    overall_status = _derive_overall_status(machine_ok=machine_ok, manual_status=args.manual_status)

    report: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": base,
        "project_id": args.project_id,
        "operator": args.operator,
        "scenario": args.scenario,
        "manual_status": args.manual_status,
        "machine_ok": machine_ok,
        "overall_status": overall_status,
        "notes": args.notes,
        "machine_checks": checks,
        "manual_checklist": [
            {"step": "Send /status", "expectation": "Correct project/session; no bridge/runtime errors"},
            {"step": "Send /sessions", "expectation": "Active session list is rendered correctly"},
            {"step": "Send plain text (for example: ping bridge)", "expectation": "Bot response received; no duplicate side effects"},
            {"step": "Run one bootstrap flow", "expectation": "Trace contains task_id, run_id, report endpoint, optional PR URL"},
        ],
        "raw": {
            "bridge_status": {"http_status": bridge_status, "payload": bridge_payload},
            "health": {"http_status": health_status, "payload": health_payload},
            "ops_status": {"http_status": ops_status, "payload": ops_payload},
            "remediate_stale_dry_run": {"http_status": remediate_status, "payload": remediate_payload},
        },
    }

    out_json = Path(args.out_json).expanduser()
    out_md = Path(args.out_md).expanduser()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_markdown(report), encoding="utf-8")

    print(json.dumps({"status": overall_status, "out_json": str(out_json), "out_md": str(out_md)}, ensure_ascii=False))
    return 1 if overall_status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())

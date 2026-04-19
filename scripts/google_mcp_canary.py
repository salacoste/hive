#!/usr/bin/env python3
"""Run Google MCP smoke canary and persist ops artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

DEFAULT_ARTIFACT_DIR = Path("docs/ops/google-canary")
SMOKE_SCRIPT = Path("scripts/google_mcp_smoke_test.py")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _run_smoke(dotenv: str, write: bool) -> tuple[int, dict[str, Any], str]:
    cmd = [sys.executable, str(SMOKE_SCRIPT), "--dotenv", dotenv]
    if write:
        cmd.append("--write")
    p = subprocess.run(cmd, check=False, capture_output=True, text=True)
    raw = (p.stdout or "").strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {"raw_output": raw}
    return int(p.returncode), payload, (p.stderr or "").strip()


def _render_md(doc: dict[str, Any]) -> str:
    checks = doc.get("checks") or []
    lines = [
        "# Google MCP Canary Latest",
        "",
        f"- generated_at: `{doc.get('generated_at')}`",
        f"- status: `{doc.get('status')}`",
        f"- mode: `{doc.get('mode')}`",
        f"- failed: `{doc.get('failed')}`",
        "",
        "## Checks",
        "",
    ]
    for item in checks:
        tool = str(item.get("tool") or "-")
        ok = bool(item.get("ok"))
        mark = "OK" if ok else "FAIL"
        if ok:
            lines.append(f"- [{mark}] `{tool}`")
        else:
            err = str(item.get("error") or "unknown")
            lines.append(f"- [{mark}] `{tool}`: `{err}`")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Google MCP canary + persist artifact")
    parser.add_argument("--dotenv", default=".env", help="Path to env file for smoke script")
    parser.add_argument("--write", action="store_true", help="Run write checks (docs/sheets create)")
    parser.add_argument(
        "--artifact-dir",
        default=str(DEFAULT_ARTIFACT_DIR),
        help=f"Artifact dir (default: {DEFAULT_ARTIFACT_DIR})",
    )
    args = parser.parse_args(argv)

    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()
    ts_path = artifact_dir / f"google-canary-{stamp}.json"
    latest_json = artifact_dir / "latest.json"
    latest_md = artifact_dir / "latest.md"

    code, payload, stderr = _run_smoke(args.dotenv, args.write)
    checks = payload.get("checks") if isinstance(payload, dict) else None
    if not isinstance(checks, list):
        checks = []
    failed = int(payload.get("failed") or 0) if isinstance(payload, dict) else 1
    status = "ok" if code == 0 else "degraded"

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(SMOKE_SCRIPT),
        "mode": "write" if args.write else "read_only",
        "status": status,
        "failed": failed,
        "checks": checks,
        "stderr": stderr,
    }
    serialized = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    ts_path.write_text(serialized, encoding="utf-8")
    latest_json.write_text(serialized, encoding="utf-8")
    latest_md.write_text(_render_md(doc), encoding="utf-8")

    print(f"[ok] wrote {ts_path}")
    print(f"[ok] wrote {latest_json}")
    print(f"[ok] wrote {latest_md}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

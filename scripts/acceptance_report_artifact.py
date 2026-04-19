#!/usr/bin/env python3
"""Write acceptance gate report artifact from current runtime snapshot."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

BASE = "http://localhost:8787"
OUT_DIR = Path("docs/ops/acceptance-reports")


def _get(path: str) -> dict:
    with urlopen(f"{BASE}{path}", timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S")

    health = _get("/api/health")
    ops = _get("/api/autonomous/ops/status?project_id=default&include_runs=true")
    tg = _get("/api/telegram/bridge/status")

    artifact = {
        "generated_at": now.isoformat(timespec="seconds"),
        "health": {
            "status": health.get("status"),
            "sessions": health.get("sessions"),
            "agents_loaded": health.get("agents_loaded"),
        },
        "ops": {
            "status": ops.get("status"),
            "runs_total": (((ops.get("summary") or {}).get("runs_total")) if isinstance(ops, dict) else None),
            "stuck_runs_total": (((ops.get("alerts") or {}).get("stuck_runs_total")) if isinstance(ops, dict) else None),
            "no_progress_projects_total": (((ops.get("alerts") or {}).get("no_progress_projects_total")) if isinstance(ops, dict) else None),
        },
        "telegram_bridge": {
            "status": tg.get("status"),
            "running": ((tg.get("bridge") or {}).get("running") if isinstance(tg, dict) else None),
            "poller_owner": ((tg.get("bridge") or {}).get("poller_owner") if isinstance(tg, dict) else None),
        },
    }

    out = OUT_DIR / f"acceptance-report-{stamp}.json"
    out.write_text(json.dumps(artifact, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    latest = OUT_DIR / "latest.json"
    latest.write_text(json.dumps(artifact, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    print(f"[ok] wrote acceptance artifact: {out}")
    print(f"[ok] updated latest: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

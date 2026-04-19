#!/usr/bin/env python3
"""Generate backlog status snapshot artifacts from backlog_status.py --json output."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

BACKLOG_STATUS_SCRIPT = Path("scripts/backlog_status.py")
OUTPUT_DIR = Path("docs/ops/backlog-status")


def _load_status_payload() -> dict:
    result = subprocess.run(
        [sys.executable, str(BACKLOG_STATUS_SCRIPT), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"backlog_status.py --json failed with code {result.returncode}")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("backlog_status.py --json returned non-object payload")
    return payload


def main() -> int:
    print("== Backlog Status Artifact ==")
    if not BACKLOG_STATUS_SCRIPT.exists():
        print(f"[fail] missing script: {BACKLOG_STATUS_SCRIPT}")
        return 1

    try:
        payload = _load_status_payload()
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        print(f"[fail] cannot build backlog status payload: {exc}")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    ts_path = OUTPUT_DIR / f"backlog-status-{stamp}.json"
    latest_path = OUTPUT_DIR / "latest.json"

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(BACKLOG_STATUS_SCRIPT),
        "status": payload,
    }
    serialized = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"

    ts_path.write_text(serialized, encoding="utf-8")
    latest_path.write_text(serialized, encoding="utf-8")

    print(f"[ok] wrote {ts_path}")
    print(f"[ok] wrote {latest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

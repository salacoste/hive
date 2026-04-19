#!/usr/bin/env python3
"""Enforce historical acceptance quality thresholds."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

OUT_DIR = Path("docs/ops/acceptance-reports")
PATTERN = "acceptance-report-*.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_pass(entry: dict[str, Any]) -> bool:
    health = entry.get("health") or {}
    ops = entry.get("ops") or {}
    tg = entry.get("telegram_bridge") or {}
    return (
        health.get("status") == "ok"
        and ops.get("status") == "ok"
        and (ops.get("stuck_runs_total") in (0, None))
        and (ops.get("no_progress_projects_total") in (0, None))
        and tg.get("status") == "ok"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard against acceptance regressions in recent history")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days")
    parser.add_argument("--max-fail", type=int, default=0, help="Max allowed failing artifacts in window")
    parser.add_argument("--min-pass-rate", type=float, default=1.0, help="Minimum required pass rate in window (0..1)")
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty window without failing")
    args = parser.parse_args()

    if args.days < 1:
        raise SystemExit("[error] --days must be >= 1")
    if args.max_fail < 0:
        raise SystemExit("[error] --max-fail must be >= 0")
    if args.min_pass_rate < 0 or args.min_pass_rate > 1:
        raise SystemExit("[error] --min-pass-rate must be in range [0,1]")

    files = sorted(OUT_DIR.glob(PATTERN), reverse=True)
    cutoff = datetime.now() - timedelta(days=args.days)
    rows: list[tuple[datetime, Path, bool]] = []
    for path in files:
        data = _load(path)
        raw_ts = data.get("generated_at")
        if not isinstance(raw_ts, str):
            continue
        try:
            ts = datetime.fromisoformat(raw_ts)
        except ValueError:
            continue
        if ts < cutoff:
            continue
        rows.append((ts, path, _is_pass(data)))

    total = len(rows)
    passed = sum(1 for _, _, ok in rows if ok)
    failed = total - passed
    pass_rate = (passed / total) if total > 0 else 0.0

    print("== Acceptance Regression Guard ==")
    print(f"window_days={args.days}")
    print(f"artifacts_total={total}")
    print(f"pass={passed}")
    print(f"fail={failed}")
    print(f"pass_rate={pass_rate:.4f}")
    print(f"max_fail={args.max_fail}")
    print(f"min_pass_rate={args.min_pass_rate:.4f}")

    if total == 0:
        if args.allow_empty:
            print("[ok] empty window allowed")
            return 0
        print("[fail] no artifacts in window")
        return 1

    if failed > args.max_fail:
        print("[fail] fail-count threshold exceeded")
        return 1
    if pass_rate < args.min_pass_rate:
        print("[fail] pass-rate threshold exceeded")
        return 1

    print("[ok] regression guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

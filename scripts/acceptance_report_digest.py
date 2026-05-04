#!/usr/bin/env python3
"""Summarize recent acceptance report artifacts for operator review."""

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
    parser = argparse.ArgumentParser(description="Summarize acceptance report artifacts")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7)")
    parser.add_argument("--limit", type=int, default=20, help="Max recent records to print (default: 20)")
    parser.add_argument("--out-json", type=Path, default=None, help="Optional path to write digest JSON")
    parser.add_argument("--out-md", type=Path, default=None, help="Optional path to write digest Markdown")
    args = parser.parse_args()

    if args.days < 1:
        raise SystemExit("[error] --days must be >= 1")
    if args.limit < 1:
        raise SystemExit("[error] --limit must be >= 1")

    files = sorted(OUT_DIR.glob(PATTERN), reverse=True)
    cutoff = datetime.now() - timedelta(days=args.days)
    rows: list[tuple[datetime, Path, dict[str, Any], bool]] = []

    for path in files:
        data = _load(path)
        ts_raw = data.get("generated_at")
        if not isinstance(ts_raw, str):
            continue
        try:
            ts = datetime.fromisoformat(ts_raw)
        except ValueError:
            continue
        if ts < cutoff:
            continue
        rows.append((ts, path, data, _is_pass(data)))

    total = len(rows)
    passed = sum(1 for _, _, _, ok in rows if ok)
    failed = total - passed
    telegram_conflict_warning_records = 0
    telegram_conflict_max_count = 0

    recent_records: list[dict[str, Any]] = []
    print("== Acceptance Report Digest ==")
    print(f"window_days={args.days}")
    print(f"artifacts_total={total}")
    print(f"pass={passed}")
    print(f"fail={failed}")
    print("recent:")
    for ts, path, data, ok in rows[: args.limit]:
        health = (data.get("health") or {}).get("status")
        ops = (data.get("ops") or {}).get("status")
        tg_payload = data.get("telegram_bridge") or {}
        tg = tg_payload.get("status")
        tg_conflicts = int(tg_payload.get("poll_conflict_409_count") or 0)
        tg_conflict_warning = bool(tg_payload.get("poll_conflict_warning_active"))
        telegram_conflict_max_count = max(telegram_conflict_max_count, tg_conflicts)
        if tg_conflict_warning:
            telegram_conflict_warning_records += 1
        mark = "PASS" if ok else "FAIL"
        recent_records.append(
            {
                "generated_at": ts.isoformat(timespec="seconds"),
                "result": mark,
                "health": health,
                "ops": ops,
                "telegram": tg,
                "telegram_conflicts_409": tg_conflicts,
                "telegram_conflict_warning": tg_conflict_warning,
                "artifact": path.name,
            }
        )
        print(
            " - "
            f"{ts.isoformat(timespec='seconds')} [{mark}] health={health} ops={ops} tg={tg} "
            f"tg409={tg_conflicts} tg409warn={tg_conflict_warning} :: {path.name}"
        )

    print(f"telegram_conflict_warning_records={telegram_conflict_warning_records}")
    print(f"telegram_conflict_max_count={telegram_conflict_max_count}")

    summary = {
        "window_days": args.days,
        "artifacts_total": total,
        "pass": passed,
        "fail": failed,
        "telegram_conflict_warning_records": telegram_conflict_warning_records,
        "telegram_conflict_max_count": telegram_conflict_max_count,
        "recent": recent_records,
    }

    if args.out_json is not None:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        print(f"out_json={args.out_json}")

    if args.out_md is not None:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Acceptance Digest",
            "",
            f"- window_days: `{args.days}`",
            f"- artifacts_total: `{total}`",
            f"- pass: `{passed}`",
            f"- fail: `{failed}`",
            "",
            "| generated_at | result | health | ops | telegram | artifact |",
            "|---|---|---|---|---|---|",
        ]
        for item in recent_records:
            lines.append(
                f"| {item['generated_at']} | {item['result']} | {item['health']} | {item['ops']} | {item['telegram']} | {item['artifact']} |"
            )
        args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"out_md={args.out_md}")

    if total == 0:
        print("[warn] no artifacts in selected window")
    else:
        print("[ok] digest generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

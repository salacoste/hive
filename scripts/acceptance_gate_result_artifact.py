#!/usr/bin/env python3
"""Build machine-readable acceptance gate step artifact with release matrix."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

MUST_CHECKS = (
    "acceptance toolchain self-check (minimal regression)",
    "mcp health summary",
    "ops status health (project)",
    "api health contract",
    "api ops status contract",
    "api telegram bridge status contract",
)

SHOULD_CHECKS = (
    "backlog validator",
    "runtime parity",
    "run-cycle compact report",
    "acceptance report artifact",
)

NICE_CHECKS = (
    "local prod checklist",
    "acceptance docs navigation check",
    "acceptance presets smoke",
    "autonomous delivery e2e smoke",
)


def _bucket_status(steps: dict[str, str], names: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in names:
        status = steps.get(name)
        if status == "ok":
            out[name] = "pass"
        elif status == "fail":
            out[name] = "fail"
        else:
            out[name] = "missing"
    return out


def _count(bucket: dict[str, str], target: str) -> int:
    return sum(1 for status in bucket.values() if status == target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write acceptance gate results artifact")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--project-id", required=True, help="Project id used in gate run")
    parser.add_argument("--ok", type=int, required=True, help="Total ok steps")
    parser.add_argument("--failed", type=int, required=True, help="Total failed steps")
    args = parser.parse_args()

    steps: list[dict[str, str]] = []
    step_map: dict[str, str] = {}
    for raw in sys.stdin.read().splitlines():
        if "\t" not in raw:
            continue
        name, status = raw.split("\t", 1)
        clean_name = name.strip()
        clean_status = status.strip()
        if not clean_name:
            continue
        if clean_status not in {"ok", "fail"}:
            continue
        steps.append({"name": clean_name, "status": clean_status})
        step_map[clean_name] = clean_status

    must = _bucket_status(step_map, MUST_CHECKS)
    should = _bucket_status(step_map, SHOULD_CHECKS)
    nice = _bucket_status(step_map, NICE_CHECKS)
    must_failed = _count(must, "fail")
    must_missing = _count(must, "missing")

    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_id": args.project_id,
        "summary": {
            "ok": args.ok,
            "failed": args.failed,
            "steps_total": len(steps),
        },
        "steps": steps,
        "release_matrix": {
            "status": "pass" if (must_failed == 0 and must_missing == 0) else "fail",
            "must": must,
            "should": should,
            "nice": nice,
            "must_passed": _count(must, "pass"),
            "must_total": len(MUST_CHECKS),
            "must_failed": must_failed,
            "must_missing": must_missing,
        },
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] wrote gate artifact: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

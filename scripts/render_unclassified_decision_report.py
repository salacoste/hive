#!/usr/bin/env python3
"""Render a markdown report for unclassified upstream delta decisions."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

DECISIONS_PATH = Path("docs/ops/upstream-unclassified-decisions.json")
UPSTREAM_DELTA_STATUS = Path(__file__).resolve().with_name("upstream_delta_status.py")


def _load_delta_helpers():
    spec = spec_from_file_location("upstream_delta_status", UPSTREAM_DELTA_STATUS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {UPSTREAM_DELTA_STATUS}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.classify_paths, module.parse_name_status


def _load_unclassified_paths(base_ref: str, target_ref: str) -> list[str]:
    classify_paths, parse_name_status = _load_delta_helpers()
    result = subprocess.run(
        ["git", "diff", "--name-status", f"{base_ref}..{target_ref}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "(no stderr)"
        raise RuntimeError(f"git diff failed: {stderr}")
    entries = parse_name_status(result.stdout)
    classified = classify_paths([entry.path for entry in entries])
    return classified["other_unclassified"]


def _load_decisions(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("decisions file must be a JSON object")
    return data


def render_report(unclassified: list[str], decisions: dict[str, dict]) -> str:
    counter = Counter()
    for path in unclassified:
        decision = str(decisions.get(path, {}).get("decision", "missing"))
        counter[decision] += 1

    lines: list[str] = [
        "# Upstream Unclassified Decision Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Total unclassified paths: {len(unclassified)}",
        "",
        "## Decision Summary",
        "",
        f"- already-absorbed: {counter.get('already-absorbed', 0)}",
        f"- defer: {counter.get('defer', 0)}",
        f"- merge-now: {counter.get('merge-now', 0)}",
        f"- missing: {counter.get('missing', 0)}",
        "",
        "## Path Decisions",
        "",
        "| Path | Decision | Backlog Items |",
        "|---|---|---|",
    ]
    for path in unclassified:
        payload = decisions.get(path, {})
        decision = str(payload.get("decision", "missing"))
        backlog_items = payload.get("backlog_items", [])
        if isinstance(backlog_items, list):
            backlog_text = ", ".join(str(item) for item in backlog_items)
        else:
            backlog_text = ""
        lines.append(f"| `{path}` | `{decision}` | `{backlog_text}` |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render/check unclassified decision report")
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--target-ref", default="origin/main")
    parser.add_argument("--decisions", default=str(DECISIONS_PATH))
    parser.add_argument("--write", default="")
    parser.add_argument("--check", default="")
    args = parser.parse_args()

    try:
        unclassified = _load_unclassified_paths(args.base_ref, args.target_ref)
        decisions = _load_decisions(Path(args.decisions))
    except Exception as exc:
        print(f"[fail] {exc}")
        return 1

    report = render_report(unclassified, decisions)

    if args.write:
        target = Path(args.write)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report, encoding="utf-8")
        print(f"[ok] wrote report: {target}")

    if args.check:
        target = Path(args.check)
        if not target.exists():
            print(f"[fail] report not found: {target}")
            return 1
        existing = target.read_text(encoding="utf-8")

        # Generated timestamp line is expected to differ run-to-run.
        def _normalize(text: str) -> str:
            return "\n".join(line for line in text.splitlines() if not line.startswith("Generated:"))

        if _normalize(existing) != _normalize(report):
            print(f"[fail] report out of sync: {target}")
            print("[hint] run with --write to refresh")
            return 1
        print(f"[ok] report in sync: {target}")

    if not args.write and not args.check:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

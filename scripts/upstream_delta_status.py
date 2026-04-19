#!/usr/bin/env python3
"""Summarize unresolved upstream delta and classify files into risk buckets."""

from __future__ import annotations

import argparse
import json
import subprocess
from typing import NamedTuple

BUCKET_A_LOW_RISK: set[str] = {
    ".gitignore",
    "README.md",
    "core/framework/runtime/README.md",
    "docs/browser-extension-setup.html",
    "docs/configuration.md",
    "docs/developer-guide.md",
    "docs/environment-setup.md",
}

BUCKET_B_MEDIUM_RISK: set[str] = {
    "core/framework/agents/queen/nodes/__init__.py",
    "core/framework/agents/queen/queen_memory_v2.py",
    "core/framework/agents/queen/recall_selector.py",
    "core/framework/graph/context.py",
    "core/framework/graph/executor.py",
    "core/framework/graph/worker_agent.py",
    "core/framework/runtime/agent_runtime.py",
    "core/framework/runtime/execution_stream.py",
    "core/framework/tools/queen_lifecycle_tools.py",
    "core/tests/test_event_bus.py",
    "core/tests/test_queen_memory.py",
}

BUCKET_C_HIGH_RISK: set[str] = {
    "core/framework/agents/queen/queen_memory.py",
    "core/framework/tools/queen_memory_tools.py",
}


class DeltaEntry(NamedTuple):
    status: str
    path: str


def parse_name_status(raw: str) -> list[DeltaEntry]:
    """Parse `git diff --name-status` output into normalized entries."""
    entries: list[DeltaEntry] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        # Rename/copy lines: status old_path new_path -> use new path
        path = parts[-1]
        entries.append(DeltaEntry(status=status, path=path))
    return entries


def classify_paths(paths: list[str]) -> dict[str, list[str]]:
    """Classify paths into wave buckets."""
    bucket_a: list[str] = []
    bucket_b: list[str] = []
    bucket_c: list[str] = []
    other: list[str] = []
    for path in sorted(set(paths)):
        if path in BUCKET_A_LOW_RISK:
            bucket_a.append(path)
        elif path in BUCKET_B_MEDIUM_RISK:
            bucket_b.append(path)
        elif path in BUCKET_C_HIGH_RISK:
            bucket_c.append(path)
        else:
            other.append(path)
    return {
        "bucket_a_low_risk": bucket_a,
        "bucket_b_medium_risk": bucket_b,
        "bucket_c_high_risk": bucket_c,
        "other_unclassified": other,
    }


def run_git_name_status(base_ref: str, target_ref: str) -> str:
    result = subprocess.run(
        ["git", "diff", "--name-status", f"{base_ref}..{target_ref}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "(no stderr)"
        raise RuntimeError(f"git diff failed: {stderr}")
    return result.stdout


def build_report(base_ref: str, target_ref: str, raw: str) -> dict[str, object]:
    entries = parse_name_status(raw)
    paths = [entry.path for entry in entries]
    buckets = classify_paths(paths)
    return {
        "base_ref": base_ref,
        "target_ref": target_ref,
        "total_entries": len(entries),
        "buckets": {
            key: {"count": len(values), "paths": values} for key, values in buckets.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Upstream delta bucket status report")
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--target-ref", default="origin/main")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    try:
        raw = run_git_name_status(args.base_ref, args.target_ref)
    except RuntimeError as exc:
        print(f"[fail] {exc}")
        return 1

    report = build_report(args.base_ref, args.target_ref, raw)
    if args.json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    print("== Upstream Delta Bucket Status ==")
    print(f"base_ref={report['base_ref']}")
    print(f"target_ref={report['target_ref']}")
    print(f"total_entries={report['total_entries']}")
    for key, payload in report["buckets"].items():
        print(f"{key}: {payload['count']}")
        for path in payload["paths"]:
            print(f" - {path}")
    print("[ok] upstream delta status generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

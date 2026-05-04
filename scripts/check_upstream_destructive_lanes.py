#!/usr/bin/env python3
"""Fail when upstream diff contains destructive deletes in protected lanes.

This script is intended for upstream-sync safety gates. It inspects
``git diff --name-status <base>..<upstream>`` and fails if there are delete
records (``D``) under protected path prefixes, unless explicitly allowlisted.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_REF = "HEAD"
DEFAULT_UPSTREAM_REF = "upstream/main"

PROTECTED_PREFIXES: tuple[str, ...] = (
    ".github/workflows/",
    "scripts/",
    "docs/autonomous-factory/",
    "docs/ops/",
    "ai-proxy-docs/",
)


@dataclass(frozen=True)
class DeleteRecord:
    status: str
    path: str


def _is_under_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def parse_name_status(text: str) -> list[DeleteRecord]:
    """Parse git --name-status output into deletion records only."""
    records: list[DeleteRecord] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0].strip().upper()
        if status.startswith("D"):
            records.append(DeleteRecord(status=status, path=parts[1].strip()))
    return records


def find_protected_deletes(
    records: list[DeleteRecord],
    *,
    protected_prefixes: tuple[str, ...],
    allow_delete_prefixes: tuple[str, ...],
) -> list[DeleteRecord]:
    flagged: list[DeleteRecord] = []
    for rec in records:
        if not _is_under_any(rec.path, protected_prefixes):
            continue
        if allow_delete_prefixes and _is_under_any(rec.path, allow_delete_prefixes):
            continue
        flagged.append(rec)
    return flagged


def _run_git_diff(base_ref: str, upstream_ref: str) -> str:
    cmd = ["git", "diff", "--name-status", f"{base_ref}..{upstream_ref}"]
    cp = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return cp.stdout


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-ref", default=DEFAULT_BASE_REF)
    p.add_argument("--upstream-ref", default=DEFAULT_UPSTREAM_REF)
    p.add_argument(
        "--allow-delete-prefix",
        action="append",
        default=[],
        help="Path prefix allowed for deletes inside protected lanes (repeatable).",
    )
    p.add_argument("--json", action="store_true", help="Emit machine-readable output.")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        diff_text = _run_git_diff(args.base_ref, args.upstream_ref)
    except subprocess.CalledProcessError as exc:
        message = f"git diff failed: exit={exc.returncode}"
        if args.json:
            print(json.dumps({"ok": False, "error": message}))
        else:
            print(f"[fail] {message}")
        return 2

    deletes = parse_name_status(diff_text)
    flagged = find_protected_deletes(
        deletes,
        protected_prefixes=PROTECTED_PREFIXES,
        allow_delete_prefixes=tuple(str(x).strip() for x in args.allow_delete_prefix if str(x).strip()),
    )

    payload = {
        "ok": len(flagged) == 0,
        "base_ref": args.base_ref,
        "upstream_ref": args.upstream_ref,
        "protected_prefixes": list(PROTECTED_PREFIXES),
        "allow_delete_prefixes": args.allow_delete_prefix,
        "delete_total": len(deletes),
        "flagged_total": len(flagged),
        "flagged_paths": [r.path for r in flagged],
    }
    if args.json:
        print(json.dumps(payload))
    else:
        if payload["ok"]:
            print(
                "[ok] no protected destructive deletes: "
                f"base={args.base_ref} upstream={args.upstream_ref} delete_total={len(deletes)}"
            )
        else:
            print(
                "[fail] protected destructive deletes detected: "
                f"base={args.base_ref} upstream={args.upstream_ref} flagged_total={len(flagged)}"
            )
            for rec in flagged[:50]:
                print(f" - {rec.path}")
            if len(flagged) > 50:
                print(f" - ... and {len(flagged) - 50} more")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

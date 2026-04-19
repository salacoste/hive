#!/usr/bin/env python3
"""Validate that script commands referenced in runbook exist in repository."""

from __future__ import annotations

import re
import sys
from pathlib import Path

RUNBOOK = Path("docs/LOCAL_PROD_RUNBOOK.md")
SCRIPT_CMD_RE = re.compile(r"(?:\./)?(scripts/[A-Za-z0-9_./-]+\.(?:sh|py))")


def _extract_refs(text: str) -> list[str]:
    refs: set[str] = set()
    for line in text.splitlines():
        for m in SCRIPT_CMD_RE.finditer(line):
            refs.add(m.group(1))
    return sorted(refs)


def main() -> int:
    if not RUNBOOK.exists():
        print(f"[fail] runbook not found: {RUNBOOK}")
        return 2

    text = RUNBOOK.read_text(encoding="utf-8")
    refs = _extract_refs(text)
    missing: list[str] = []

    for rel in refs:
        p = Path(rel)
        if not p.exists():
            missing.append(rel)

    print("== Runbook Sync Check ==")
    print(f"runbook={RUNBOOK}")
    print(f"script_refs={len(refs)}")

    if missing:
        print(f"[fail] missing script refs: {len(missing)}")
        for rel in missing:
            print(f" - {rel}")
        return 1

    print("[ok] all referenced scripts exist")
    if refs:
        print("refs:")
        for rel in refs:
            print(f" - {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

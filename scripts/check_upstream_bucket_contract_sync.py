#!/usr/bin/env python3
"""Ensure upstream bucket mappings stay synced between docs and automation."""

from __future__ import annotations

import re
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

INVENTORY_DOC = Path("docs/autonomous-factory/16-upstream-wave2-delta-inventory.md")
UPSTREAM_DELTA_STATUS = Path(__file__).resolve().with_name("upstream_delta_status.py")

_SECTION_MARKERS = {
    "a": "### Bucket A: Low-Risk Docs/Meta Sync",
    "b": "### Bucket B: Medium-Risk Runtime/Graph Changes",
    "c": "### Bucket C: High-Risk Removals / Architecture Shift",
}
_PATH_LINE_RE = re.compile(r"^-\s+`(?P<path>[^`]+)`(?:\s+.*)?$")


def _load_bucket_constants() -> tuple[set[str], set[str], set[str]]:
    spec = spec_from_file_location("upstream_delta_status", UPSTREAM_DELTA_STATUS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {UPSTREAM_DELTA_STATUS}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return (
        set(module.BUCKET_A_LOW_RISK),
        set(module.BUCKET_B_MEDIUM_RISK),
        set(module.BUCKET_C_HIGH_RISK),
    )


def _extract_section_paths(text: str, marker: str) -> set[str]:
    lines = text.splitlines()
    in_section = False
    started_list = False
    result: set[str] = set()

    for line in lines:
        if line.strip() == marker:
            in_section = True
            continue
        if in_section and line.startswith("### "):
            break
        if not in_section:
            continue

        m = _PATH_LINE_RE.match(line.strip())
        if m:
            result.add(m.group("path"))
            started_list = True
            continue
        if started_list and line.strip() and not line.strip().startswith("-"):
            break

    return result


def extract_doc_buckets(text: str) -> dict[str, set[str]]:
    return {
        "a": _extract_section_paths(text, _SECTION_MARKERS["a"]),
        "b": _extract_section_paths(text, _SECTION_MARKERS["b"]),
        "c": _extract_section_paths(text, _SECTION_MARKERS["c"]),
    }


def main() -> int:
    if not INVENTORY_DOC.exists():
        print(f"[fail] inventory doc not found: {INVENTORY_DOC}")
        return 1

    text = INVENTORY_DOC.read_text(encoding="utf-8")
    doc_buckets = extract_doc_buckets(text)
    bucket_a, bucket_b, bucket_c = _load_bucket_constants()
    code_buckets = {
        "a": bucket_a,
        "b": bucket_b,
        "c": bucket_c,
    }

    failed = False
    print("== Upstream Bucket Contract Sync Check ==")
    for key in ("a", "b", "c"):
        doc_set = doc_buckets[key]
        code_set = code_buckets[key]
        missing_in_doc = sorted(code_set - doc_set)
        missing_in_code = sorted(doc_set - code_set)
        if missing_in_doc or missing_in_code:
            failed = True
            print(f"[fail] bucket_{key} contract drift")
            if missing_in_doc:
                print(f" - in code only: {missing_in_doc}")
            if missing_in_code:
                print(f" - in doc only: {missing_in_code}")
        else:
            print(f"[ok] bucket_{key} in sync ({len(doc_set)} paths)")

    if failed:
        print("[fail] upstream bucket contract sync check failed")
        return 1
    print("[ok] upstream bucket contract sync check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

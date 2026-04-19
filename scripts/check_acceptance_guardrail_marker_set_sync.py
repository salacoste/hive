#!/usr/bin/env python3
"""Ensure guardrail marker sets are synchronized across acceptance checkers."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

GUARDRAILS_MODULE_PATH = Path("scripts/check_acceptance_guardrails_sync.py")
DOCS_NAV_MODULE_PATH = Path("scripts/check_acceptance_docs_navigation.py")
DOCS_MAP_PATH = Path("docs/ops/acceptance-automation-map.md")
EXCLUDED_MARKERS = {
    "scripts/check_acceptance_docs_navigation.py",
    "scripts/check_acceptance_guardrails_sync.py",
    "scripts/check_acceptance_guardrail_marker_set_sync.py",
}


def _load_module(path: Path, name: str):
    spec = spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load module: {path}")
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    print("== Acceptance Guardrail Marker-Set Sync Check ==")
    if not GUARDRAILS_MODULE_PATH.exists() or not DOCS_NAV_MODULE_PATH.exists():
        print("[fail] required checker modules are missing")
        return 1

    guardrails = _load_module(GUARDRAILS_MODULE_PATH, "check_acceptance_guardrails_sync")
    docs_nav = _load_module(DOCS_NAV_MODULE_PATH, "check_acceptance_docs_navigation")

    guardrail_set = {m for m in getattr(guardrails, "GUARDRAIL_SCRIPTS", []) if m not in EXCLUDED_MARKERS}
    docs_map_needles: list[str] = []
    for path, needles in getattr(docs_nav, "CHECKS", []):
        if Path(path) == DOCS_MAP_PATH:
            docs_map_needles = list(needles)
            break
    docs_guardrail_set = {
        n
        for n in docs_map_needles
        if (n.startswith("scripts/check_acceptance_") or n.startswith("scripts/check_backlog_"))
        and n not in EXCLUDED_MARKERS
    }

    missing_in_docs = sorted(guardrail_set - docs_guardrail_set)
    missing_in_guardrails = sorted(docs_guardrail_set - guardrail_set)

    fail = 0
    if missing_in_docs:
        print(f"[fail] markers present in guardrails checker but missing in docs-nav checker: {len(missing_in_docs)}")
        for item in missing_in_docs:
            print(f" - {item}")
        fail += 1
    else:
        print("[ok] all guardrails markers exist in docs-nav checker set")

    if missing_in_guardrails:
        print(f"[fail] markers present in docs-nav checker but missing in guardrails checker: {len(missing_in_guardrails)}")
        for item in missing_in_guardrails:
            print(f" - {item}")
        fail += 1
    else:
        print("[ok] all docs-nav guardrail markers exist in guardrails checker set")

    if fail:
        print(f"[fail] guardrail marker-set sync failed: {fail} issue group(s)")
        return 1
    print("[ok] acceptance guardrail marker sets are in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate that every unclassified upstream delta path has a triage decision."""

from __future__ import annotations

import json
import subprocess
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

DECISIONS_PATH = Path("docs/ops/upstream-unclassified-decisions.json")
ALLOWED_DECISIONS = {"merge-now", "defer", "already-absorbed"}
UPSTREAM_DELTA_STATUS = Path(__file__).resolve().with_name("upstream_delta_status.py")


def _load_delta_helpers():
    spec = spec_from_file_location("upstream_delta_status", UPSTREAM_DELTA_STATUS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {UPSTREAM_DELTA_STATUS}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.classify_paths, module.parse_name_status


def load_decisions(path: Path) -> dict[str, dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("decisions file must be a JSON object")
    result: dict[str, dict[str, object]] = {}
    for key, payload in data.items():
        if not isinstance(payload, dict):
            raise ValueError(f"decision payload for {key} must be object")
        decision = str(payload.get("decision", "")).strip()
        rationale = str(payload.get("rationale", "")).strip()
        backlog_items = payload.get("backlog_items")
        validation = payload.get("validation")
        if decision not in ALLOWED_DECISIONS:
            raise ValueError(
                f"invalid decision for {key}: {decision!r}; allowed={sorted(ALLOWED_DECISIONS)}"
            )
        if not rationale:
            raise ValueError(f"missing rationale for {key}")
        if not isinstance(backlog_items, list) or not backlog_items:
            raise ValueError(f"missing backlog_items for {key}")
        if not all(isinstance(item, int) and item > 0 for item in backlog_items):
            raise ValueError(f"invalid backlog_items for {key}: {backlog_items!r}")
        if not isinstance(validation, list) or not validation:
            raise ValueError(f"missing validation commands for {key}")
        if not all(isinstance(cmd, str) and cmd.strip() for cmd in validation):
            raise ValueError(f"invalid validation commands for {key}: {validation!r}")
        result[key] = {
            "decision": decision,
            "rationale": rationale,
            "backlog_items": backlog_items,
            "validation": validation,
        }
    return result


def get_unclassified_paths(base_ref: str, target_ref: str) -> list[str]:
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


def main() -> int:
    print("== Unclassified Delta Decision Coverage Check ==")
    if not DECISIONS_PATH.exists():
        print(f"[fail] decisions file not found: {DECISIONS_PATH}")
        return 1

    try:
        decisions = load_decisions(DECISIONS_PATH)
    except Exception as exc:
        print(f"[fail] invalid decisions file: {exc}")
        return 1

    try:
        unclassified = get_unclassified_paths("HEAD", "origin/main")
    except RuntimeError as exc:
        print(f"[fail] {exc}")
        return 1

    unclassified_set = set(unclassified)
    decision_set = set(decisions)
    missing = sorted(unclassified_set - decision_set)
    stale = sorted(decision_set - unclassified_set)

    if missing:
        print(f"[fail] missing decisions for {len(missing)} path(s)")
        for path in missing:
            print(f" - {path}")
        return 1

    print(f"[ok] covered_unclassified={len(unclassified)}")
    if stale:
        print(f"[warn] stale decision entries={len(stale)}")
        for path in stale:
            print(f" - {path}")
    else:
        print("[ok] stale_decisions=0")

    tally: dict[str, int] = {name: 0 for name in sorted(ALLOWED_DECISIONS)}
    for path in unclassified:
        tally[decisions[path]["decision"]] += 1
    print("decision_tally=" + ", ".join(f"{k}:{v}" for k, v in tally.items()))
    print("[ok] unclassified decision coverage passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

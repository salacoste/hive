"""Project policy resolution (global policy + per-project overrides)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_FACTORY_POLICY: dict[str, Any] = {
    "factory": {
        "default_risk_tier": "low",
        "retry_limit_per_stage": 2,
    },
    "risk_policy": {
        "low": {
            "plan_approval_required": False,
            "run_approval_required": False,
            "merge_approval_required": True,
        },
        "medium": {
            "plan_approval_required": True,
            "run_approval_required": True,
            "merge_approval_required": True,
        },
        "high": {
            "plan_approval_required": True,
            "run_approval_required": True,
            "merge_approval_required": True,
        },
        "critical": {
            "allowed": False,
        },
    },
}


def _merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)
        else:
            out[k] = v
    return out


def load_factory_policy() -> dict[str, Any]:
    policy_path = os.environ.get("HIVE_FACTORY_POLICY_PATH", "").strip()
    candidate_paths = []
    if policy_path:
        candidate_paths.append(Path(policy_path))
    candidate_paths.append(Path.cwd() / "automation" / "hive.factory-policy.yaml")
    candidate_paths.append(Path.cwd() / "docs" / "autonomous-factory" / "templates" / "factory-policy.yaml")

    for p in candidate_paths:
        if not p.exists():
            continue
        try:
            loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                return _merge_dict(DEFAULT_FACTORY_POLICY, loaded)
        except OSError:
            continue
    return DEFAULT_FACTORY_POLICY


def normalize_policy_overrides(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw or {}
    out: dict[str, Any] = {}
    if "risk_tier" in src:
        rt = str(src.get("risk_tier") or "").strip().lower()
        if rt:
            if rt not in {"low", "medium", "high", "critical"}:
                raise ValueError("risk_tier must be one of: low, medium, high, critical")
            out["risk_tier"] = rt
    if "retry_limit_per_stage" in src:
        rv = src.get("retry_limit_per_stage")
        if rv is None or rv == "":
            out["retry_limit_per_stage"] = None
        else:
            parsed = int(rv)
            if parsed < 0:
                raise ValueError("retry_limit_per_stage must be >= 0")
            out["retry_limit_per_stage"] = parsed
    if "budget_limit_usd_monthly" in src:
        bv = src.get("budget_limit_usd_monthly")
        if bv is None or bv == "":
            out["budget_limit_usd_monthly"] = None
        else:
            parsed = float(bv)
            if parsed < 0:
                raise ValueError("budget_limit_usd_monthly must be >= 0")
            out["budget_limit_usd_monthly"] = parsed
    return out


def resolve_effective_policy(project: dict[str, Any] | None) -> dict[str, Any]:
    project = project or {}
    global_policy = load_factory_policy()
    overrides = normalize_policy_overrides(project.get("policy_overrides") or {})

    factory = global_policy.get("factory", {}) if isinstance(global_policy, dict) else {}
    risk_policy = global_policy.get("risk_policy", {}) if isinstance(global_policy, dict) else {}

    risk_tier = overrides.get("risk_tier") or factory.get("default_risk_tier") or "low"
    retry_limit = overrides.get("retry_limit_per_stage")
    if retry_limit is None:
        retry_limit = factory.get("retry_limit_per_stage", 2)
    budget = overrides.get("budget_limit_usd_monthly")
    if budget is None:
        budget = factory.get("budget_limit_usd_monthly")

    risk_controls = risk_policy.get(risk_tier, risk_policy.get("low", {}))
    return {
        "project_id": project.get("id"),
        "global_policy": global_policy,
        "overrides": overrides,
        "effective": {
            "risk_tier": risk_tier,
            "retry_limit_per_stage": retry_limit,
            "budget_limit_usd_monthly": budget,
            "risk_controls": risk_controls,
        },
    }

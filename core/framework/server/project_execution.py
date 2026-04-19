"""Project execution template resolution and normalization helpers."""

from __future__ import annotations

from typing import Any

from framework.server.project_policy import normalize_policy_overrides, resolve_effective_policy

DEFAULT_EXECUTION_TEMPLATE: dict[str, Any] = {
    "default_flow": [
        {"stage": "design", "mode": "queen_plan", "model_profile": "strategy_heavy"},
        {"stage": "implement", "mode": "worker_execute", "model_profile": "implementation"},
        {"stage": "review", "mode": "worker_review", "model_profile": "review_validation"},
        {"stage": "validate", "mode": "worker_validate", "model_profile": "review_validation"},
    ],
    "retry_policy": {
        "max_retries_per_stage": 1,
        "escalate_on": ["review", "validate"],
    },
}


def _normalize_stage(item: object, *, idx: int) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError(f"default_flow[{idx}] must be an object")
    stage = str(item.get("stage") or "").strip().lower()
    mode = str(item.get("mode") or "").strip()
    profile = str(item.get("model_profile") or "").strip()
    if not stage:
        raise ValueError(f"default_flow[{idx}].stage is required")
    if not mode:
        raise ValueError(f"default_flow[{idx}].mode is required")
    if not profile:
        raise ValueError(f"default_flow[{idx}].model_profile is required")
    return {"stage": stage, "mode": mode, "model_profile": profile}


def normalize_execution_template(
    value: object,
    *,
    allow_null_fields: bool = False,
) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("execution_template must be an object")

    out: dict[str, Any] = {}
    if "default_flow" in value:
        raw_flow = value.get("default_flow")
        if raw_flow is None:
            if allow_null_fields:
                out["default_flow"] = None
            else:
                raise ValueError("default_flow cannot be null")
        else:
            if not isinstance(raw_flow, list) or not raw_flow:
                raise ValueError("default_flow must be a non-empty array")
            out["default_flow"] = [_normalize_stage(item, idx=i) for i, item in enumerate(raw_flow)]

    if "retry_policy" in value:
        raw_retry = value.get("retry_policy")
        if raw_retry is None:
            if allow_null_fields:
                out["retry_policy"] = None
            else:
                raise ValueError("retry_policy cannot be null")
        else:
            if not isinstance(raw_retry, dict):
                raise ValueError("retry_policy must be an object")
            rp: dict[str, Any] = {}
            if "max_retries_per_stage" in raw_retry:
                rv = raw_retry.get("max_retries_per_stage")
                if rv is None:
                    rp["max_retries_per_stage"] = None
                else:
                    parsed = int(rv)
                    if parsed < 0:
                        raise ValueError("max_retries_per_stage must be >= 0")
                    rp["max_retries_per_stage"] = parsed
            if "escalate_on" in raw_retry:
                raw_escalate = raw_retry.get("escalate_on")
                if raw_escalate is None:
                    rp["escalate_on"] = None
                elif not isinstance(raw_escalate, list):
                    raise ValueError("escalate_on must be an array")
                else:
                    rp["escalate_on"] = [
                        str(stage).strip().lower() for stage in raw_escalate if str(stage).strip()
                    ]
            out["retry_policy"] = rp

    if "github" in value:
        raw_github = value.get("github")
        if raw_github is None:
            if allow_null_fields:
                out["github"] = None
            else:
                raise ValueError("github cannot be null")
        else:
            if not isinstance(raw_github, dict):
                raise ValueError("github must be an object")
            gh: dict[str, Any] = {}
            for key in ("default_ref", "default_branch", "ref", "branch"):
                if key in raw_github:
                    gv = raw_github.get(key)
                    if gv is None:
                        gh[key] = None
                    else:
                        gs = str(gv).strip()
                        if not gs:
                            raise ValueError(f"github.{key} cannot be empty")
                        gh[key] = gs
            if "no_checks_policy" in raw_github:
                pv = raw_github.get("no_checks_policy")
                if pv is None:
                    gh["no_checks_policy"] = None
                else:
                    ps = str(pv).strip().lower()
                    if ps not in {"error", "success", "manual_pending", "manual", "defer", "pass", "ok"}:
                        raise ValueError(
                            "github.no_checks_policy must be one of: "
                            "error, success, manual_pending"
                        )
                    gh["no_checks_policy"] = ps
            out["github"] = gh

    for key in ("default_ref", "default_branch", "ref", "branch", "no_checks_policy"):
        if key in value:
            raw = value.get(key)
            if raw is None:
                out[key] = None
            else:
                sv = str(raw).strip()
                if not sv:
                    raise ValueError(f"{key} cannot be empty")
                if key == "no_checks_policy":
                    sv_l = sv.lower()
                    if sv_l not in {"error", "success", "manual_pending", "manual", "defer", "pass", "ok"}:
                        raise ValueError(
                            "no_checks_policy must be one of: error, success, manual_pending"
                        )
                    out[key] = sv_l
                else:
                    out[key] = sv

    return out


def _merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        elif value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def resolve_execution_template(project: dict[str, Any]) -> dict[str, Any]:
    project = project or {}
    overrides = normalize_execution_template(project.get("execution_template") or {})
    default_template = _merge_dict(DEFAULT_EXECUTION_TEMPLATE, {})
    effective_template = _merge_dict(default_template, overrides)

    raw_binding = project.get("policy_binding")
    if isinstance(raw_binding, dict):
        binding = normalize_policy_overrides(raw_binding)
    else:
        binding = normalize_policy_overrides(project.get("policy_overrides") or {})

    policy_project = dict(project)
    policy_project["policy_overrides"] = binding
    policy = resolve_effective_policy(policy_project)

    return {
        "project_id": project.get("id"),
        "defaults": {
            "execution_template": default_template,
            "policy_binding": {},
        },
        "execution_template": overrides,
        "policy_binding": binding,
        "effective": {
            "execution_template": effective_template,
            "policy": policy.get("effective", {}),
        },
    }

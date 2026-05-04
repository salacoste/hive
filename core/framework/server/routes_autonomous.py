"""Autonomous development pipeline routes (backlog -> execution -> review -> validation)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from aiohttp import web

from framework.server.app import APP_KEY_MANAGER
from framework.server.autonomous_pipeline import AutonomousPipelineStore, STAGES
from framework.server.project_execution import resolve_execution_template

APP_KEY_AUTONOMOUS_STORE: web.AppKey[AutonomousPipelineStore] = web.AppKey(
    "autonomous_pipeline_store", AutonomousPipelineStore
)

INTAKE_DELIVERY_MODES = {"patch_only", "pr_only", "patch_and_pr"}


class GitHubApiError(RuntimeError):
    """Structured GitHub API failure used for actionable HTTP responses."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _get_store(request: web.Request) -> AutonomousPipelineStore:
    return request.app[APP_KEY_AUTONOMOUS_STORE]


def _require_project(manager: Any, project_id: str) -> dict[str, Any] | None:
    project = manager.get_project(project_id)
    if project is None:
        return None
    return project


def _parse_bool_param(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_optional_positive_int(value: Any, *, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{field_name} must be a positive integer") from e
    if parsed <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return parsed


def _intake_contract_enabled(value: Any = None) -> bool:
    if value is not None:
        return _parse_bool_param(value, default=False)
    raw = os.environ.get("HIVE_AUTONOMOUS_INTAKE_STRICT", "").strip()
    return _parse_bool_param(raw, default=False)


def _validate_intake_contract(body: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    normalized: dict[str, Any] = {}

    title = str(body.get("title") or "").strip()
    goal = str(body.get("goal") or "").strip()
    criteria_raw = body.get("acceptance_criteria")
    constraints_raw = body.get("constraints")
    delivery_mode = str(body.get("delivery_mode") or "").strip().lower()

    if not title:
        errors.append("title is required")
    elif len(title) < 6:
        errors.append("title must be at least 6 characters")
    else:
        normalized["title"] = title

    if not goal:
        errors.append("goal is required")
    elif len(goal) < 12:
        errors.append("goal must be at least 12 characters with concrete outcome")
    else:
        normalized["goal"] = goal

    if not isinstance(criteria_raw, list):
        errors.append("acceptance_criteria must be an array of non-empty strings")
    else:
        criteria = [str(x).strip() for x in criteria_raw if str(x).strip()]
        if not criteria:
            errors.append("acceptance_criteria cannot be empty")
        else:
            normalized["acceptance_criteria"] = criteria

    if not isinstance(constraints_raw, list):
        errors.append("constraints must be an array of non-empty strings")
    else:
        constraints = [str(x).strip() for x in constraints_raw if str(x).strip()]
        if not constraints:
            errors.append("constraints cannot be empty")
        else:
            normalized["constraints"] = constraints

    if delivery_mode not in INTAKE_DELIVERY_MODES:
        errors.append("delivery_mode must be one of: patch_only, pr_only, patch_and_pr")
    else:
        normalized["delivery_mode"] = delivery_mode

    return errors, normalized


def _validate_task_status(value: str) -> str:
    status = value.strip().lower()
    if status not in {"todo", "in_progress", "done", "blocked"}:
        raise ValueError("status must be one of: todo, in_progress, done, blocked")
    return status


def _validate_priority(value: str) -> str:
    priority = value.strip().lower()
    if priority not in {"low", "medium", "high", "critical"}:
        raise ValueError("priority must be one of: low, medium, high, critical")
    return priority


def _normalize_string_array(raw: Any, *, field_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} must be an array")
    return [str(x).strip() for x in raw if str(x).strip()]


def _resolve_validation_contract(
    *,
    project: dict[str, Any],
    repository: str,
    service_matrix: list[str],
    requested_mode: str | None,
) -> tuple[str, str]:
    explicit = (requested_mode or "").strip().lower()
    if explicit:
        if explicit not in {"ci_first", "local_or_ci"}:
            raise ValueError("validation_mode must be one of: ci_first, local_or_ci")
        return explicit, "explicit_request"

    if service_matrix:
        return "ci_first", "service_matrix_declared"
    if not _docker_lane_enabled():
        return "ci_first", "docker_lane_disabled"
    if not shutil.which("docker"):
        return "ci_first", "docker_cli_unavailable_in_runtime"
    workspace_path = str(project.get("workspace_path") or "").strip()
    if not workspace_path:
        return "ci_first", "workspace_not_bound_for_local_integration"
    if not repository.strip():
        return "local_or_ci", "local_workspace_without_repository"
    return "local_or_ci", "local_runtime_available"


def _stage_policy(project: dict[str, Any]) -> dict[str, Any]:
    execution = resolve_execution_template(project)
    effective = execution.get("effective", {}).get("execution_template", {})
    retry_policy = effective.get("retry_policy", {}) if isinstance(effective, dict) else {}
    max_retries = int(retry_policy.get("max_retries_per_stage", 1) or 0)
    escalate_on = retry_policy.get("escalate_on", [])
    escalate = {str(x).strip().lower() for x in escalate_on if str(x).strip()}
    return {"max_retries": max_retries, "escalate_on": escalate}


def _run_guardrails(project: dict[str, Any]) -> dict[str, Any]:
    execution = resolve_execution_template(project)
    effective = execution.get("effective", {}).get("execution_template", {})
    guardrails = effective.get("run_guardrails", {}) if isinstance(effective, dict) else {}
    if not isinstance(guardrails, dict):
        guardrails = {}

    def _to_int(raw: Any, default: int, *, minimum: int, maximum: int) -> int:
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, parsed))

    stop_action = str(guardrails.get("stop_action") or "failed").strip().lower()
    if stop_action not in {"failed", "escalated"}:
        stop_action = "failed"
    fail_on_unknown_action = _parse_bool_param(guardrails.get("fail_on_unknown_action"), default=True)
    return {
        "max_run_seconds": _to_int(
            guardrails.get("max_run_seconds", 1800), 1800, minimum=60, maximum=86400
        ),
        "max_tool_calls_execution_stage": _to_int(
            guardrails.get("max_tool_calls_execution_stage", 150), 150, minimum=1, maximum=20000
        ),
        "max_loop_ticks_per_run": _to_int(
            guardrails.get("max_loop_ticks_per_run", 24), 24, minimum=1, maximum=1000
        ),
        "stop_action": stop_action,
        "fail_on_unknown_action": fail_on_unknown_action,
        "container_only": _parse_bool_param(guardrails.get("container_only"), default=True),
    }


def _task_contract(task: Any) -> dict[str, Any]:
    return {
        "task_id": task.id,
        "title": task.title,
        "goal": task.goal,
        "acceptance_criteria": list(task.acceptance_criteria),
        "priority": task.priority,
        "repository": task.repository,
        "branch": task.branch,
        "required_checks": list(getattr(task, "required_checks", []) or []),
        "workflow": str(getattr(task, "workflow", "") or "").strip(),
        "service_matrix": list(getattr(task, "service_matrix", []) or []),
        "validation_mode": str(getattr(task, "validation_mode", "") or "").strip(),
        "validation_reason": str(getattr(task, "validation_reason", "") or "").strip(),
    }


def _priority_rank(value: str) -> int:
    v = (value or "").strip().lower()
    if v == "critical":
        return 4
    if v == "high":
        return 3
    if v == "medium":
        return 2
    if v == "low":
        return 1
    return 0


def _pick_next_task(tasks: list[Any]) -> Any | None:
    if not tasks:
        return None
    # Prefer higher priority first, then FIFO among equal priorities.
    ordered = sorted(
        tasks,
        key=lambda t: (-_priority_rank(str(getattr(t, "priority", ""))), float(getattr(t, "created_at", 0.0))),
    )
    return ordered[0]


def _project_has_active_run(store: AutonomousPipelineStore, project_id: str) -> Any | None:
    runs = store.list_runs(project_id=project_id)
    for run in runs:
        if run.status in {"queued", "in_progress"}:
            return run
    return None


async def _create_run_for_task(
    *,
    manager: Any,
    store: AutonomousPipelineStore,
    project_id: str,
    task: Any,
    auto_start: bool,
    session_id: str,
) -> tuple[Any | None, str | None, int]:
    run = store.create_run(project_id=project_id, task_id=task.id)
    task_status = "in_progress" if task.status == "todo" else task.status
    store.update_task(task.id, {"status": task_status})

    if auto_start:
        stage_states = dict(run.stage_states)
        stage_states[run.current_stage] = "in_progress"
        run = store.update_run(run.id, {"status": "in_progress", "stage_states": stage_states}) or run

    if auto_start and session_id:
        session = manager.get_session(session_id)
        if session is None:
            return None, f"Session '{session_id}' not found", 404
        if getattr(session, "project_id", None) != project_id:
            return None, "session project mismatch", 409
        if session.graph_runtime is None:
            return None, "No graph loaded in this session", 503
        worker_graph_id = str(getattr(session.graph_runtime, "_graph_id", "") or "").strip()

        execution_id = await session.graph_runtime.trigger(
            "default",
            {
                "task": task.goal,
                "topic": task.goal,
                "user_request": task.goal,
                "contract": _task_contract(task),
                "source": "autonomous_pipeline",
                "autonomous_mode": True,
            },
            session_state={"resume_session_id": session.id},
        )
        stage_states = dict(run.stage_states)
        stage_states["execution"] = "running"
        artifacts = dict(run.artifacts)
        stage_artifacts = dict(artifacts.get("stages", {}))
        stage_artifacts["execution"] = {
            "result": "running",
            "timestamp": time.time(),
            "output": {
                "execution_id": execution_id,
                "session_id": session.id,
                "worker_graph_id": worker_graph_id,
            },
            "attempt": 1,
        }
        artifacts["stages"] = stage_artifacts
        run = store.update_run(
            run.id,
            {
                "status": "in_progress",
                "stage_states": stage_states,
                "artifacts": artifacts,
            },
        ) or run
    return run, None, 201


def _normalize_checks(raw: object) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("checks must be an array")
    checks: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"checks[{idx}] must be an object")
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValueError(f"checks[{idx}].name is required")
        passed_raw = item.get("passed")
        if passed_raw is None and "status" in item:
            status_raw = str(item.get("status") or "").strip().lower()
            if status_raw in {"passed", "pass", "success", "ok"}:
                passed = True
            elif status_raw in {"failed", "fail", "failure", "error"}:
                passed = False
            else:
                raise ValueError(f"checks[{idx}].status must be passed/failed-like")
        elif isinstance(passed_raw, bool):
            passed = passed_raw
        elif isinstance(passed_raw, (int, float)):
            passed = bool(passed_raw)
        elif isinstance(passed_raw, str):
            p = passed_raw.strip().lower()
            if p in {"true", "1", "yes", "y", "passed", "pass", "success", "ok"}:
                passed = True
            elif p in {"false", "0", "no", "n", "failed", "fail", "failure", "error"}:
                passed = False
            else:
                raise ValueError(f"checks[{idx}].passed must be boolean-like")
        else:
            passed = False
        severity = str(item.get("severity") or "error").strip().lower() or "error"
        checks.append(
            {
                "name": name,
                "passed": passed,
                "severity": severity,
                "details": str(item.get("details") or "").strip(),
            }
        )
    return checks


def _checks_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(checks)
    passed = sum(1 for c in checks if c.get("passed"))
    failed = total - passed
    failures = [c for c in checks if not c.get("passed")]
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "all_passed": failed == 0,
        "failures": failures,
    }


def _count_by(items: list[Any], attr: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        key = str(getattr(item, attr, "") or "unknown")
        out[key] = out.get(key, 0) + 1
    return out


def _auto_next_fallback_mode() -> str:
    mode = os.environ.get("HIVE_AUTONOMOUS_AUTO_NEXT_FALLBACK", "error").strip().lower()
    if mode in {"manual", "manual_pending", "defer"}:
        return "manual_pending"
    return "error"


def _stuck_run_threshold_seconds() -> int:
    raw = os.environ.get("HIVE_AUTONOMOUS_STUCK_RUN_SECONDS", "").strip()
    if not raw:
        return 1800
    try:
        value = int(raw)
    except ValueError:
        return 1800
    return max(60, value)


def _no_progress_threshold_seconds() -> int:
    raw = os.environ.get("HIVE_AUTONOMOUS_NO_PROGRESS_SECONDS", "").strip()
    if not raw:
        return 900
    try:
        value = int(raw)
    except ValueError:
        return 900
    return max(60, value)


def _loop_stale_threshold_seconds() -> int:
    raw = os.environ.get("HIVE_AUTONOMOUS_LOOP_STALE_SECONDS", "").strip()
    if not raw:
        return 600
    try:
        value = int(raw)
    except ValueError:
        return 600
    return max(60, value)


def _docker_lane_enabled() -> bool:
    return _parse_bool_param(os.environ.get("HIVE_AUTONOMOUS_DOCKER_LANE_ENABLED"), default=False)


def _docker_lane_profile() -> str:
    profile = os.environ.get("HIVE_AUTONOMOUS_DOCKER_LANE_PROFILE", "docker_local").strip()
    return profile or "docker_local"


def _docker_lane_health_timeout_seconds() -> int:
    raw = os.environ.get("HIVE_AUTONOMOUS_DOCKER_LANE_HEALTHCHECK_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 5
    try:
        value = int(raw)
    except ValueError:
        return 5
    return max(1, min(30, value))


def _docker_lane_health() -> dict[str, Any]:
    enabled = _docker_lane_enabled()
    profile = _docker_lane_profile()
    docker_path = shutil.which("docker")
    payload: dict[str, Any] = {
        "enabled": enabled,
        "profile": profile,
        "feature_flag": "HIVE_AUTONOMOUS_DOCKER_LANE_ENABLED",
        "docker_cli_available": bool(docker_path),
        "docker_cli_path": docker_path or "",
        "healthcheck_timeout_seconds": _docker_lane_health_timeout_seconds(),
        "ready": False,
        "status": "disabled",
        "reason": "feature_flag_disabled",
    }
    if not enabled:
        return payload

    if not docker_path:
        payload.update(
            {
                "status": "degraded",
                "reason": "docker_cli_unavailable",
            }
        )
        return payload

    timeout_seconds = int(payload["healthcheck_timeout_seconds"])
    try:
        result = subprocess.run(
            [docker_path, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        payload.update(
            {
                "status": "degraded",
                "reason": "docker_info_timeout",
            }
        )
        return payload
    except Exception as exc:
        payload.update(
            {
                "status": "degraded",
                "reason": "docker_info_exec_failed",
                "error": str(exc)[:240],
            }
        )
        return payload

    if int(result.returncode) != 0:
        detail = (result.stderr or result.stdout or "").strip()
        payload.update(
            {
                "status": "degraded",
                "reason": "docker_daemon_unreachable",
                "error": detail[:240] if detail else "",
            }
        )
        return payload

    version = (result.stdout or "").strip().strip('"')
    payload.update(
        {
            "status": "ready",
            "reason": "ok",
            "ready": True,
            "server_version": version,
        }
    )
    return payload


def _autonomous_loop_state_path() -> Path:
    raw = os.environ.get("HIVE_AUTONOMOUS_LOOP_STATE_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hive" / "server" / "autonomous_loop_state.json"


def _read_autonomous_loop_state() -> dict[str, Any] | None:
    path = _autonomous_loop_state_path()
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _acceptance_gate_results_shared_path() -> Path:
    raw = os.environ.get("HIVE_ACCEPTANCE_GATE_SHARED_JSON_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hive" / "server" / "acceptance" / "gate-latest.json"


def _to_int_or_none(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _read_release_matrix_snapshot() -> dict[str, Any]:
    path = _acceptance_gate_results_shared_path()
    payload: dict[str, Any] = {}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = {}

    matrix_raw = payload.get("release_matrix")
    matrix = matrix_raw if isinstance(matrix_raw, dict) else {}
    status = str(matrix.get("status") or "").strip().lower()
    if status not in {"pass", "fail"}:
        status = "unknown"
    generated_at = str(payload.get("generated_at") or matrix.get("generated_at") or "").strip() or None
    return {
        "path": str(path),
        "status": status,
        "must_passed": _to_int_or_none(matrix.get("must_passed")),
        "must_total": _to_int_or_none(matrix.get("must_total")),
        "must_failed": _to_int_or_none(matrix.get("must_failed")),
        "must_missing": _to_int_or_none(matrix.get("must_missing")),
        "generated_at": generated_at,
    }


def _append_run_event(
    *,
    store: AutonomousPipelineStore,
    run: Any,
    event_type: str,
    data: dict[str, Any],
) -> Any | None:
    artifacts = dict(run.artifacts)
    events = artifacts.get("events", [])
    if not isinstance(events, list):
        events = []
    events.append(
        {
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        }
    )
    artifacts["events"] = events
    return store.update_run(run.id, {"artifacts": artifacts})


def _count_execution_tool_calls(
    session_id: str,
    execution_id: str,
    *,
    worker_graph_id: str = "",
) -> int:
    events_path = Path.home() / ".hive" / "queen" / "session" / session_id / "events.jsonl"
    if not events_path.exists():
        return 0
    count = 0
    tool_started_types = {"tool_call_started", "tool_started"}
    try:
        with open(events_path, encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    evt = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(evt, dict):
                    continue
                if str(evt.get("execution_id") or "").strip() != execution_id:
                    continue
                evt_graph_id = str(evt.get("graph_id") or "").strip()
                if worker_graph_id and evt_graph_id and evt_graph_id != worker_graph_id:
                    continue
                evt_type = str(evt.get("type") or "").strip().lower()
                if evt_type in tool_started_types:
                    count += 1
    except OSError:
        return 0
    return count


def _apply_guardrail_terminal_stop(
    *,
    store: AutonomousPipelineStore,
    run: Any,
    stage: str,
    stop_action: str,
    reason: str,
    details: dict[str, Any] | None = None,
) -> Any | None:
    stop_status = "escalated" if stop_action == "escalated" else "failed"
    stage_states = dict(run.stage_states)
    stage_states[stage] = stop_status
    artifacts = dict(run.artifacts) if isinstance(run.artifacts, dict) else {}
    stages = dict(artifacts.get("stages") or {}) if isinstance(artifacts.get("stages"), dict) else {}
    stage_obj = dict(stages.get(stage) or {}) if isinstance(stages.get(stage), dict) else {}
    stage_obj.update(
        {
            "result": stop_status,
            "timestamp": time.time(),
            "summary": f"Guardrail stop: {reason}",
            "source": "guardrail_stop",
            "output": {"reason": reason, "details": details or {}},
            "guardrail": {"reason": reason, **(details or {})},
        }
    )
    stages[stage] = stage_obj
    artifacts["stages"] = stages
    report = dict(artifacts.get("report") or {}) if isinstance(artifacts.get("report"), dict) else {}
    report["guardrail_stop"] = {
        "reason": reason,
        "stage": stage,
        "status": stop_status,
        "details": details or {},
        "timestamp": time.time(),
    }
    artifacts["report"] = report
    updated = store.update_run(
        run.id,
        {
            "status": stop_status,
            "current_stage": stage,
            "stage_states": stage_states,
            "artifacts": artifacts,
            "finished_at": time.time(),
        },
    )
    if updated is not None:
        _append_run_event(
            store=store,
            run=updated,
            event_type="guardrail_stop",
            data={"reason": reason, "stage": stage, "status": stop_status, "details": details or {}},
        )
    return updated


def _is_execution_active(session: Any, execution_id: str, *, worker_graph_id: str = "") -> bool:
    runtime = getattr(session, "graph_runtime", None)
    if runtime is None:
        return False
    graph_ids = [worker_graph_id] if worker_graph_id else list(runtime.list_graphs())
    for graph_id in graph_ids:
        reg = runtime.get_graph_registration(graph_id)
        if reg is None:
            continue
        for stream in reg.streams.values():
            active_ids = getattr(stream, "active_execution_ids", set()) or set()
            if execution_id in active_ids:
                return True
    return False


def _read_last_execution_terminal_event(
    session_id: str,
    execution_id: str,
    *,
    worker_graph_id: str = "",
) -> dict[str, Any] | None:
    events_path = Path.home() / ".hive" / "queen" / "session" / session_id / "events.jsonl"
    if not events_path.exists():
        return None
    last: dict[str, Any] | None = None
    try:
        with open(events_path, encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    evt = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(evt, dict):
                    continue
                if str(evt.get("execution_id") or "").strip() != execution_id:
                    continue
                evt_graph_id = str(evt.get("graph_id") or "").strip()
                if worker_graph_id and evt_graph_id and evt_graph_id != worker_graph_id:
                    continue
                evt_type = str(evt.get("type") or "").strip().lower()
                if evt_type in {"execution_completed", "execution_failed", "execution_paused"}:
                    last = evt
    except OSError:
        return None
    return last


def _read_last_terminal_worker_completion_event(
    session_id: str,
    execution_id: str,
    *,
    worker_graph_id: str = "",
    terminal_worker_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    resolved_terminal_ids = {str(x).strip() for x in (terminal_worker_ids or set()) if str(x).strip()}
    if not resolved_terminal_ids:
        return None
    events_path = Path.home() / ".hive" / "queen" / "session" / session_id / "events.jsonl"
    if not events_path.exists():
        return None
    last: dict[str, Any] | None = None
    try:
        with open(events_path, encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    evt = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(evt, dict):
                    continue
                if str(evt.get("execution_id") or "").strip() != execution_id:
                    continue
                evt_graph_id = str(evt.get("graph_id") or "").strip()
                if worker_graph_id and evt_graph_id and evt_graph_id != worker_graph_id:
                    continue
                evt_type = str(evt.get("type") or "").strip().lower()
                if evt_type != "worker_completed":
                    continue
                data = evt.get("data")
                if not isinstance(data, dict):
                    continue
                worker_id = str(data.get("worker_id") or "").strip()
                if worker_id in resolved_terminal_ids:
                    last = evt
    except OSError:
        return None
    return last


def _read_last_worker_completed_event(
    session_id: str,
    execution_id: str,
    *,
    worker_graph_id: str = "",
) -> dict[str, Any] | None:
    events_path = Path.home() / ".hive" / "queen" / "session" / session_id / "events.jsonl"
    if not events_path.exists():
        return None
    last: dict[str, Any] | None = None
    try:
        with open(events_path, encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    evt = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(evt, dict):
                    continue
                if str(evt.get("execution_id") or "").strip() != execution_id:
                    continue
                evt_graph_id = str(evt.get("graph_id") or "").strip()
                if worker_graph_id and evt_graph_id and evt_graph_id != worker_graph_id:
                    continue
                evt_type = str(evt.get("type") or "").strip().lower()
                if evt_type == "worker_completed":
                    last = evt
    except OSError:
        return None
    return last


def _resolve_execution_outcome(manager: Any, run: Any) -> dict[str, Any]:
    artifacts = run.artifacts if isinstance(run.artifacts, dict) else {}
    stages = artifacts.get("stages", {})
    execution_stage = stages.get("execution", {}) if isinstance(stages, dict) else {}
    output = execution_stage.get("output", {}) if isinstance(execution_stage, dict) else {}
    if not isinstance(output, dict):
        output = {}
    execution_id = str(output.get("execution_id") or "").strip()
    session_id = str(output.get("session_id") or "").strip()
    worker_graph_id = str(output.get("worker_graph_id") or "").strip()
    if not execution_id or not session_id:
        # Backward/alternate artifact shape from stage evaluation path.
        nested = output.get("execution")
        if isinstance(nested, dict):
            execution_id = execution_id or str(nested.get("execution_id") or "").strip()
            session_id = session_id or str(nested.get("session_id") or "").strip()
            worker_graph_id = worker_graph_id or str(nested.get("worker_graph_id") or "").strip()
    if not execution_id or not session_id:
        return {
            "status": "unknown",
            "reason": "missing_execution_reference",
            "execution_id": execution_id,
            "session_id": session_id,
            "worker_graph_id": worker_graph_id,
        }

    session = manager.get_session(session_id)
    terminal = _read_last_execution_terminal_event(
        session_id,
        execution_id,
        worker_graph_id=worker_graph_id,
    )
    if terminal is not None:
        evt_type = str(terminal.get("type") or "").strip().lower()
        if evt_type == "execution_completed":
            status = "completed"
        elif evt_type == "execution_failed":
            status = "failed"
        else:
            status = "paused"
        return {
            "status": status,
            "execution_id": execution_id,
            "session_id": session_id,
            "worker_graph_id": worker_graph_id,
            "event": terminal,
        }

    terminal_worker_ids: set[str] = set()
    if session is not None and worker_graph_id:
        reg = getattr(session.graph_runtime, "get_graph_registration", lambda _gid: None)(worker_graph_id)
        graph_obj = getattr(reg, "graph", None)
        terminal_raw = getattr(graph_obj, "terminal_nodes", None)
        if isinstance(terminal_raw, (list, tuple, set)):
            terminal_worker_ids = {str(x).strip() for x in terminal_raw if str(x).strip()}
    worker_terminal = _read_last_terminal_worker_completion_event(
        session_id,
        execution_id,
        worker_graph_id=worker_graph_id,
        terminal_worker_ids=terminal_worker_ids,
    )
    if worker_terminal is not None:
        return {
            "status": "completed",
            "reason": "terminal_worker_completed_without_execution_terminal_event",
            "execution_id": execution_id,
            "session_id": session_id,
            "worker_graph_id": worker_graph_id,
            "event": worker_terminal,
        }

    if session is not None and _is_execution_active(
        session,
        execution_id,
        worker_graph_id=worker_graph_id,
    ):
        return {
            "status": "running",
            "execution_id": execution_id,
            "session_id": session_id,
            "worker_graph_id": worker_graph_id,
        }

    # Cold-restart fallback: if session is not currently loaded and we do not
    # have graph terminal metadata, infer terminality from the last worker
    # completion that produced no downstream activations.
    last_worker_completed = _read_last_worker_completed_event(
        session_id,
        execution_id,
        worker_graph_id=worker_graph_id,
    )
    if isinstance(last_worker_completed, dict):
        data = last_worker_completed.get("data")
        if isinstance(data, dict):
            activations = data.get("activations")
            if isinstance(activations, list) and len(activations) == 0:
                success = bool(data.get("success", True))
                return {
                    "status": "completed" if success else "failed",
                    "reason": "terminal_worker_inferred_from_empty_activations",
                    "execution_id": execution_id,
                    "session_id": session_id,
                    "worker_graph_id": worker_graph_id,
                    "event": last_worker_completed,
                }

    return {
        "status": "unknown",
        "reason": "no_terminal_event",
        "execution_id": execution_id,
        "session_id": session_id,
        "worker_graph_id": worker_graph_id,
    }


def _evaluate_github_for_run(
    *,
    store: AutonomousPipelineStore,
    project: dict[str, Any],
    project_id: str,
    run: Any,
    stage: str,
    repository: str,
    ref: str,
    pr_url: str,
    required_checks: list[str] | None,
    notes: str,
    summary: str,
    token: str,
    source: str,
    pr_number: int | None = None,
    post_review_summary: bool = False,
    review_summary_comment: str = "",
) -> tuple[Any | None, str | None, int]:
    valid, validation_error = _validate_github_credential(
        token=token,
        require_write=bool(post_review_summary),
    )
    if not valid:
        return None, validation_error or "GitHub credential validation failed", 400

    pr_url_for_report = pr_url or None
    try:
        resolved_repo, resolved_ref = _resolve_github_target(
            token=token,
            repository=repository,
            ref=ref,
            pr_url=pr_url,
        )
    except ValueError as e:
        return None, str(e), 400
    except RuntimeError as e:
        return None, str(e), 502

    try:
        github_eval = _fetch_github_checks(
            repository=resolved_repo,
            ref=resolved_ref,
            token=token,
            required_checks=required_checks,
        )
    except RuntimeError as e:
        return None, str(e), 502

    checks = github_eval.get("checks", [])
    if not checks:
        no_checks_policy = _github_no_checks_policy(project)
        if no_checks_policy == "manual_pending":
            return None, "No checks found for given repository/ref", 202
        if no_checks_policy != "success":
            return None, "No checks found for given repository/ref", 400
        # Explicit project/env policy: treat missing checks as successful gate.
        github_eval["checks_summary"] = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "all_passed": True,
            "failures": [],
        }
    checks_summary = github_eval.get("checks_summary", {})
    result = "success" if checks_summary.get("all_passed") else "failed"
    summary_text = summary or f"GitHub checks: {checks_summary.get('passed', 0)}/{checks_summary.get('total', 0)} passed"

    parsed_pr = _parse_github_pr_url(pr_url)
    parsed_pr_number = parsed_pr[1] if parsed_pr is not None else None
    resolved_pr_number = pr_number or parsed_pr_number
    if resolved_pr_number is not None:
        try:
            feedback = _fetch_github_pr_feedback(
                repository=resolved_repo,
                pr_number=resolved_pr_number,
                token=token,
            )
            github_eval["review_feedback"] = feedback
        except RuntimeError as e:
            github_eval["review_feedback_error"] = str(e)

    if post_review_summary:
        if stage != "review":
            return None, "post_review_summary is supported only for review stage", 400
        if resolved_pr_number is None:
            return None, "pr_number or pr_url is required to post review summary", 400
        comment_body = review_summary_comment.strip() or _build_review_summary_comment(
            checks_summary=checks_summary if isinstance(checks_summary, dict) else {},
            review_feedback=(
                github_eval.get("review_feedback")
                if isinstance(github_eval.get("review_feedback"), dict)
                else {}
            ),
        )
        try:
            posted = _github_post_issue_comment(
                repository=resolved_repo,
                pr_number=resolved_pr_number,
                token=token,
                body=comment_body,
            )
            github_eval["posted_review_comment"] = {
                "id": posted.get("id"),
                "html_url": posted.get("html_url"),
                "url": posted.get("url"),
            }
        except RuntimeError as e:
            return None, str(e), 502

    updated, err_text = _apply_stage_result(
        store=store,
        project=project,
        project_id=project_id,
        run=run,
        stage=stage,
        result=result,
        notes=notes,
        output={"github": github_eval},
        summary=summary_text,
        pr_url=pr_url_for_report,
        source=source,
        checks=checks if isinstance(checks, list) else [],
    )
    if err_text:
        status = 409 if "currently at stage" in err_text else 400
        return None, err_text, status
    return updated, None, 200


def _github_fetch_json(url: str, token: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "hive-autonomous-pipeline",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise GitHubApiError(
            f"GitHub API error ({e.code}): {detail[:300]}",
            status_code=int(e.code),
        ) from e
    except urllib.error.URLError as e:
        raise GitHubApiError(f"GitHub API unreachable: {e}") from e
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise GitHubApiError("GitHub API returned invalid JSON") from e
    if not isinstance(data, dict):
        raise GitHubApiError("GitHub API returned unexpected payload")
    return data


def _github_fetch_list_json(url: str, token: str) -> list[dict[str, Any]]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "hive-autonomous-pipeline",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise GitHubApiError(
            f"GitHub API error ({e.code}): {detail[:300]}",
            status_code=int(e.code),
        ) from e
    except urllib.error.URLError as e:
        raise GitHubApiError(f"GitHub API unreachable: {e}") from e
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise GitHubApiError("GitHub API returned invalid JSON") from e
    if not isinstance(data, list):
        raise GitHubApiError("GitHub API returned unexpected payload")
    out: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            out.append(item)
    return out


def _github_fetch_paginated_list_json(
    *,
    url: str,
    token: str,
    per_page: int = 100,
    max_pages: int = 10,
) -> list[dict[str, Any]]:
    """Fetch paginated GitHub list endpoints with deterministic upper bound."""

    page = 1
    out: list[dict[str, Any]] = []
    while page <= max_pages:
        sep = "&" if "?" in url else "?"
        page_url = f"{url}{sep}{urllib.parse.urlencode({'per_page': per_page, 'page': page})}"
        rows = _github_fetch_list_json(page_url, token)
        if not rows:
            break
        out.extend(rows)
        if len(rows) < per_page:
            break
        page += 1
    return out


def _validate_github_credential(
    *,
    token: str,
    require_write: bool = False,
) -> tuple[bool, str | None]:
    """Validate token before autonomous review/write actions."""

    try:
        _github_fetch_json("https://api.github.com/user", token)
    except GitHubApiError as e:
        if e.status_code in {401, 403}:
            return (
                False,
                "GitHub credential is invalid, expired, or lacks required access. "
                "Update `github` credential (or GITHUB_TOKEN) and retry.",
            )
        return False, f"GitHub credential validation failed: {e}"
    except RuntimeError as e:
        return False, f"GitHub credential validation failed: {e}"

    # Write permission is still enforced by the write endpoint itself
    # (issue comment POST). We keep this marker for explicit UX signalling.
    if require_write:
        return True, None
    return True, None


def _parse_github_pr_url(value: str) -> tuple[str, int] | None:
    raw = (value or "").strip()
    if not raw:
        return None
    m = re.search(
        r"github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/pull/(?P<num>\d+)",
        raw,
    )
    if not m:
        return None
    owner = m.group("owner")
    repo = m.group("repo")
    num = int(m.group("num"))
    return f"{owner}/{repo}", num


def _fetch_github_pr_feedback(
    *,
    repository: str,
    pr_number: int,
    token: str,
) -> dict[str, Any]:
    if "/" not in repository:
        raise ValueError("repository must be in owner/name format")
    if pr_number <= 0:
        raise ValueError("pr_number must be positive")

    repo = repository.strip()
    reviews = _github_fetch_paginated_list_json(
        url=f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews",
        token=token,
    )
    review_comments = _github_fetch_paginated_list_json(
        url=f"https://api.github.com/repos/{repo}/pulls/{pr_number}/comments",
        token=token,
    )
    issue_comments = _github_fetch_paginated_list_json(
        url=f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
        token=token,
    )

    states = {"approved": 0, "changes_requested": 0, "commented": 0, "dismissed": 0, "pending": 0}
    for row in reviews:
        state = str(row.get("state") or "").strip().lower()
        if state in states:
            states[state] += 1

    def _compact_review_comment(row: dict[str, Any]) -> dict[str, Any]:
        user = row.get("user") if isinstance(row.get("user"), dict) else {}
        return {
            "author": str(user.get("login") or "").strip(),
            "path": str(row.get("path") or "").strip(),
            "line": row.get("line"),
            "body": str(row.get("body") or "").strip()[:400],
            "created_at": str(row.get("created_at") or "").strip(),
        }

    def _compact_issue_comment(row: dict[str, Any]) -> dict[str, Any]:
        user = row.get("user") if isinstance(row.get("user"), dict) else {}
        return {
            "author": str(user.get("login") or "").strip(),
            "body": str(row.get("body") or "").strip()[:400],
            "created_at": str(row.get("created_at") or "").strip(),
        }

    def _compact_review(row: dict[str, Any]) -> dict[str, Any]:
        user = row.get("user") if isinstance(row.get("user"), dict) else {}
        return {
            "id": row.get("id"),
            "author": str(user.get("login") or "").strip(),
            "state": str(row.get("state") or "").strip().lower(),
            "submitted_at": str(row.get("submitted_at") or "").strip(),
            "body": str(row.get("body") or "").strip()[:400],
        }

    return {
        "pr_number": pr_number,
        "reviews_summary": {
            "total": len(reviews),
            **states,
        },
        "review_comments_summary": {"total": len(review_comments)},
        "issue_comments_summary": {"total": len(issue_comments)},
        "reviews": [_compact_review(x) for x in reviews[:20]],
        "review_comments": [_compact_review_comment(x) for x in review_comments[:20]],
        "issue_comments": [_compact_issue_comment(x) for x in issue_comments[:20]],
    }


def _build_review_summary_comment(
    *,
    checks_summary: dict[str, Any],
    review_feedback: dict[str, Any],
) -> str:
    passed = int(checks_summary.get("passed") or 0)
    total = int(checks_summary.get("total") or 0)
    reviews_summary = review_feedback.get("reviews_summary")
    reviews_summary = reviews_summary if isinstance(reviews_summary, dict) else {}
    approved = int(reviews_summary.get("approved") or 0)
    changes = int(reviews_summary.get("changes_requested") or 0)
    commented = int(reviews_summary.get("commented") or 0)
    review_comments_total = int(
        (
            review_feedback.get("review_comments_summary", {})
            if isinstance(review_feedback.get("review_comments_summary"), dict)
            else {}
        ).get("total")
        or 0
    )
    issue_comments_total = int(
        (
            review_feedback.get("issue_comments_summary", {})
            if isinstance(review_feedback.get("issue_comments_summary"), dict)
            else {}
        ).get("total")
        or 0
    )
    lines = [
        "Hive autonomous review summary",
        "",
        f"- Checks: {passed}/{total} passed",
        f"- PR reviews: approved={approved}, changes_requested={changes}, commented={commented}",
        f"- Review comments: {review_comments_total}",
        f"- Issue comments: {issue_comments_total}",
    ]
    return "\n".join(lines)


def _github_post_issue_comment(
    *,
    repository: str,
    pr_number: int,
    token: str,
    body: str,
) -> dict[str, Any]:
    payload = json.dumps({"body": body}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/issues/{pr_number}/comments",
        method="POST",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "hive-autonomous-pipeline",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub API error ({e.code}) while posting review summary: {detail[:300]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"GitHub API unreachable while posting review summary: {e}") from e
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError("GitHub API returned invalid JSON while posting review summary") from e
    if not isinstance(data, dict):
        raise RuntimeError("GitHub API returned unexpected payload while posting review summary")
    return data


def _normalize_github_repository(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", raw):
        return raw
    m = re.search(
        r"github\.com[:/](?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?$",
        raw,
    )
    if m:
        return f"{m.group('owner')}/{m.group('repo')}"
    return raw


def _project_default_ref(project: dict[str, Any], *, include_env_default: bool = True) -> str:
    candidates: list[str] = []
    exec_template = project.get("execution_template")
    if isinstance(exec_template, dict):
        github_cfg = exec_template.get("github")
        if isinstance(github_cfg, dict):
            for key in ("default_ref", "default_branch", "ref", "branch"):
                value = github_cfg.get(key)
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())
        for key in ("default_ref", "default_branch", "ref", "branch"):
            value = exec_template.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

    for key in ("default_ref", "default_branch", "branch"):
        value = project.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())

    if include_env_default:
        env_default = os.environ.get("HIVE_AUTONOMOUS_GITHUB_DEFAULT_REF", "main").strip()
        if env_default:
            candidates.append(env_default)

    return candidates[0] if candidates else ""


def _github_no_checks_policy(project: dict[str, Any]) -> str:
    candidates: list[str] = []
    exec_template = project.get("execution_template")
    if isinstance(exec_template, dict):
        github_cfg = exec_template.get("github")
        if isinstance(github_cfg, dict):
            value = github_cfg.get("no_checks_policy")
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip().lower())
        value = exec_template.get("no_checks_policy")
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip().lower())

    env_value = os.environ.get("HIVE_AUTONOMOUS_GITHUB_NO_CHECKS_POLICY", "error").strip().lower()
    if env_value:
        candidates.append(env_value)

    raw = candidates[0] if candidates else "error"
    if raw in {"success", "pass", "ok"}:
        return "success"
    if raw in {"manual_pending", "manual", "defer"}:
        return "manual_pending"
    return "error"


def _resolve_github_inputs(
    *,
    project: dict[str, Any],
    task: Any | None,
    body: dict[str, Any],
    report_pr_url: str,
) -> tuple[str, str, str]:
    repository = str(
        body.get("repository")
        or (getattr(task, "repository", "") if task is not None else "")
        or project.get("repository")
        or ""
    ).strip()
    repository = _normalize_github_repository(repository)

    pr_url = str(body.get("pr_url") or report_pr_url or "").strip()
    explicit_ref = str(
        body.get("ref")
        or body.get("branch")
        or (getattr(task, "branch", "") if task is not None else "")
        or ""
    ).strip()
    ref = explicit_ref or ("" if pr_url else _project_default_ref(project))
    return repository, ref, pr_url


def _resolve_github_target(
    *,
    token: str,
    repository: str,
    ref: str,
    pr_url: str,
) -> tuple[str, str]:
    repo = _normalize_github_repository(repository.strip())
    ref_value = ref.strip()
    pr = _parse_github_pr_url(pr_url)
    if not repo and pr is not None:
        repo = pr[0]

    if not repo:
        raise ValueError("repository is required (or provide GitHub PR URL)")
    if "/" not in repo:
        raise ValueError("repository must be in owner/name format")

    if not ref_value and pr is not None:
        pr_repo, pr_num = pr
        target_repo = repo or pr_repo
        pr_payload = _github_fetch_json(
            f"https://api.github.com/repos/{target_repo}/pulls/{pr_num}",
            token,
        )
        head = pr_payload.get("head", {})
        if not isinstance(head, dict):
            raise RuntimeError("GitHub PR payload missing head section")
        head_sha = str(head.get("sha") or "").strip()
        head_ref = str(head.get("ref") or "").strip()
        ref_value = head_sha or head_ref

    if not ref_value:
        raise ValueError("ref is required (branch/SHA or PR URL)")
    return repo, ref_value


def _fetch_github_checks(
    *,
    repository: str,
    ref: str,
    token: str,
    required_checks: list[str] | None = None,
) -> dict[str, Any]:
    repo = repository.strip()
    if "/" not in repo:
        raise ValueError("repository must be in owner/name format")
    ref_value = ref.strip()
    if not ref_value:
        raise ValueError("ref is required")

    status_payload = _github_fetch_json(
        f"https://api.github.com/repos/{repo}/commits/{ref_value}/status",
        token,
    )
    check_runs_payload = _github_fetch_json(
        f"https://api.github.com/repos/{repo}/commits/{ref_value}/check-runs",
        token,
    )

    checks: list[dict[str, Any]] = []
    contexts = status_payload.get("statuses", [])
    if isinstance(contexts, list):
        for item in contexts:
            if not isinstance(item, dict):
                continue
            name = str(item.get("context") or "").strip()
            if not name:
                continue
            state = str(item.get("state") or "").strip().lower()
            passed = state == "success"
            checks.append(
                {
                    "name": name,
                    "passed": passed,
                    "severity": "error",
                    "details": str(item.get("description") or state or "").strip(),
                }
            )

    check_runs = check_runs_payload.get("check_runs", [])
    if isinstance(check_runs, list):
        for item in check_runs:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            status = str(item.get("status") or "").strip().lower()
            conclusion = str(item.get("conclusion") or "").strip().lower()
            if status != "completed":
                passed = False
                details = f"status={status or 'unknown'}"
            else:
                passed = conclusion in {"success", "neutral", "skipped"}
                details = f"conclusion={conclusion or 'unknown'}"
            checks.append(
                {
                    "name": name,
                    "passed": passed,
                    "severity": "error",
                    "details": details,
                }
            )

    merged: dict[str, dict[str, Any]] = {}
    for item in checks:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        existing = merged.get(name)
        if existing is None:
            merged[name] = item
            continue
        # Prefer failing signal when both status and check-run report same check.
        if existing.get("passed") and not item.get("passed"):
            merged[name] = item

    out = list(merged.values())
    if required_checks:
        required = {x.strip() for x in required_checks if x.strip()}
        if required:
            out = [c for c in out if str(c.get("name") or "").strip() in required]

    return {
        "repository": repo,
        "ref": ref_value,
        "checks": out,
        "checks_summary": _checks_summary(out),
        "commit_state": status_payload.get("state"),
        "sha": status_payload.get("sha") or ref_value,
    }


def _apply_stage_result(
    *,
    store: AutonomousPipelineStore,
    project: dict[str, Any],
    project_id: str,
    run: Any,
    stage: str,
    result: str,
    notes: str,
    output: Any,
    summary: str,
    pr_url: str | None,
    source: str | None = None,
    checks: list[dict[str, Any]] | None = None,
) -> tuple[Any | None, str | None]:
    if stage not in STAGES:
        return None, f"Unknown stage: {stage}"
    if result not in {"success", "failed"}:
        return None, "result must be success or failed"
    if stage != run.current_stage:
        return None, f"Run is currently at stage '{run.current_stage}'"

    stage_states = dict(run.stage_states)
    attempts = dict(run.attempts)
    artifacts = dict(run.artifacts)
    stages_artifacts = dict(artifacts.get("stages", {}))

    attempts[stage] = int(attempts.get(stage, 0)) + 1
    stage_record: dict[str, Any] = {
        "result": result,
        "timestamp": time.time(),
        "notes": notes,
        "output": output if isinstance(output, (dict, list, str, int, float, bool)) else {},
        "attempt": attempts[stage],
    }
    if source:
        stage_record["source"] = source
    if checks:
        stage_record["checks"] = checks
        stage_record["checks_summary"] = _checks_summary(checks)
    stages_artifacts[stage] = stage_record

    policy = _stage_policy(project)
    max_retries = policy["max_retries"]
    escalate_on = policy["escalate_on"]

    next_status = "in_progress"
    next_stage = run.current_stage
    finished_at = None

    if result == "failed":
        if attempts[stage] <= max_retries:
            stage_states[stage] = "retry_pending"
        elif stage in escalate_on:
            stage_states[stage] = "escalated"
            next_status = "escalated"
            finished_at = time.time()
        else:
            stage_states[stage] = "failed"
            next_status = "failed"
            finished_at = time.time()
    else:
        stage_states[stage] = "completed"
        idx = STAGES.index(stage)
        if idx == len(STAGES) - 1:
            next_status = "completed"
            finished_at = time.time()
        else:
            next_stage = STAGES[idx + 1]
            stage_states[next_stage] = "in_progress"

    report = dict(artifacts.get("report", {}))
    task = store.get_task(run.task_id)
    contract = _task_contract(task) if task is not None else {"task_id": run.task_id}
    review_checks = stages_artifacts.get("review", {}).get("checks", [])
    validation_checks = stages_artifacts.get("validation", {}).get("checks", [])

    report.update(
        {
            "task": contract,
            "pipeline": {
                "current_stage": next_stage,
                "stage_states": stage_states,
                "attempts": attempts,
            },
            "checks": {
                "review": _checks_summary(review_checks) if isinstance(review_checks, list) else {},
                "validation": _checks_summary(validation_checks) if isinstance(validation_checks, list) else {},
            },
            "artifacts": {
                "stages": list(stages_artifacts.keys()),
            },
            "generated_at": time.time(),
        }
    )
    if summary:
        report["summary"] = summary
    if pr_url is not None:
        report["pr"] = {
            "url": pr_url or None,
            "ready": bool(pr_url) and next_status == "completed",
        }
    review_output = stages_artifacts.get("review", {}).get("output", {})
    if isinstance(review_output, dict):
        github_output = review_output.get("github")
        if isinstance(github_output, dict):
            review_feedback = github_output.get("review_feedback")
            if isinstance(review_feedback, dict):
                report["review_feedback"] = review_feedback
                reviews_summary = review_feedback.get("reviews_summary")
                review_comments_summary = review_feedback.get("review_comments_summary")
                issue_comments_summary = review_feedback.get("issue_comments_summary")
                report["review_feedback_summary"] = {
                    "ingested": True,
                    "reviews_total": (
                        int(reviews_summary.get("total") or 0) if isinstance(reviews_summary, dict) else 0
                    ),
                    "review_comments_total": (
                        int(review_comments_summary.get("total") or 0)
                        if isinstance(review_comments_summary, dict)
                        else 0
                    ),
                    "issue_comments_total": (
                        int(issue_comments_summary.get("total") or 0)
                        if isinstance(issue_comments_summary, dict)
                        else 0
                    ),
                }
            review_feedback_error = github_output.get("review_feedback_error")
            if isinstance(review_feedback_error, str) and review_feedback_error.strip():
                report["review_feedback_summary"] = {
                    "ingested": False,
                    "error": review_feedback_error.strip(),
                }
            posted_review_comment = github_output.get("posted_review_comment")
            if isinstance(posted_review_comment, dict):
                report["posted_review_comment"] = posted_review_comment
    if next_status in {"completed", "failed", "escalated"}:
        report.update(
            {
                "final_status": next_status,
                "finished_at": finished_at,
                "task_id": run.task_id,
                "project_id": project_id,
                "risks": (
                    _checks_summary(checks).get("failures", [])
                    if checks
                    else []
                ),
            }
        )

    artifacts["stages"] = stages_artifacts
    artifacts["report"] = report

    updated = store.update_run(
        run.id,
        {
            "status": next_status,
            "current_stage": next_stage,
            "stage_states": stage_states,
            "attempts": attempts,
            "artifacts": artifacts,
            "finished_at": finished_at,
        },
    )
    if updated is None:
        return None, f"Run '{run.id}' not found"

    if next_status == "completed":
        store.update_task(run.task_id, {"status": "done"})
    elif next_status in {"failed", "escalated"}:
        store.update_task(run.task_id, {"status": "blocked"})

    return updated, None


def _build_run_timeline(run: Any) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = [
        {
            "type": "run_started",
            "timestamp": float(getattr(run, "started_at", 0.0) or 0.0),
            "run_id": str(getattr(run, "id", "") or ""),
            "status": str(getattr(run, "status", "") or ""),
        }
    ]
    artifacts = run.artifacts if isinstance(run.artifacts, dict) else {}
    stages = artifacts.get("stages")
    if isinstance(stages, dict):
        for stage in STAGES:
            record = stages.get(stage)
            if not isinstance(record, dict):
                continue
            ts = float(record.get("timestamp") or 0.0)
            checks_summary = record.get("checks_summary") if isinstance(record.get("checks_summary"), dict) else {}
            row = {
                "type": "stage_result",
                "timestamp": ts,
                "stage": stage,
                "result": str(record.get("result") or "").strip().lower(),
                "attempt": int(record.get("attempt") or 0),
                "source": str(record.get("source") or "").strip() or None,
                "checks_failed": int(checks_summary.get("failed") or 0),
            }
            timeline.append(row)

    events = artifacts.get("events")
    if isinstance(events, list):
        for raw_evt in events:
            if not isinstance(raw_evt, dict):
                continue
            evt_type = str(raw_evt.get("type") or "").strip().lower()
            ts = float(raw_evt.get("timestamp") or 0.0)
            data = raw_evt.get("data") if isinstance(raw_evt.get("data"), dict) else {}
            timeline.append(
                {
                    "type": "run_event",
                    "event_type": evt_type,
                    "timestamp": ts,
                    "stage": str(data.get("stage") or "").strip() or None,
                    "status": str(data.get("status") or "").strip() or None,
                    "reason": str(data.get("reason") or "").strip() or None,
                    "source": str(data.get("source") or "").strip() or None,
                }
            )

    timeline.sort(key=lambda row: float(row.get("timestamp") or 0.0))
    return timeline


def _classify_terminal_failure(run: Any) -> dict[str, Any] | None:
    status = str(getattr(run, "status", "") or "").strip().lower()
    if status not in {"failed", "escalated"}:
        return None
    artifacts = run.artifacts if isinstance(run.artifacts, dict) else {}
    report = artifacts.get("report") if isinstance(artifacts.get("report"), dict) else {}
    stages = artifacts.get("stages") if isinstance(artifacts.get("stages"), dict) else {}
    events = artifacts.get("events") if isinstance(artifacts.get("events"), list) else []

    signals: list[str] = []
    reasons: list[str] = []

    guardrail = report.get("guardrail_stop") if isinstance(report, dict) else {}
    if isinstance(guardrail, dict):
        reason = str(guardrail.get("reason") or "").strip()
        if reason:
            reasons.append(reason)
            signals.append(f"guardrail:{reason}")

    for stage in ("review", "validation"):
        stage_rec = stages.get(stage) if isinstance(stages, dict) else {}
        checks_summary = stage_rec.get("checks_summary") if isinstance(stage_rec, dict) else {}
        if isinstance(checks_summary, dict) and int(checks_summary.get("failed") or 0) > 0:
            signals.append(f"{stage}_checks_failed")
            reasons.append(f"{stage}_checks_failed")

    for evt in events:
        if not isinstance(evt, dict):
            continue
        evt_type = str(evt.get("type") or "").strip().lower()
        data = evt.get("data") if isinstance(evt.get("data"), dict) else {}
        reason = str(data.get("reason") or "").strip()
        if evt_type == "auto_next_deferred" and reason:
            reasons.append(reason)
            signals.append(f"deferred:{reason}")
        elif evt_type == "guardrail_stop" and reason:
            reasons.append(reason)
            signals.append(f"guardrail_event:{reason}")

    summary_text = str(report.get("summary") or "").strip()
    if summary_text:
        reasons.append(summary_text)

    blob = " ".join(reasons).lower()
    category = "runtime"
    if any(x in blob for x in ["credential", "missing_github_token", "api key", "oauth", "token", "unauthorized"]):
        category = "credential"
    elif any(
        x in blob
        for x in [
            "rate limit",
            "429",
            "provider",
            "anthropic",
            "openai",
            "gemini",
            "glm",
            "model unavailable",
        ]
    ):
        category = "provider"
    elif any(
        x in blob
        for x in [
            "guardrail",
            "max_run_seconds_exceeded",
            "max_tool_calls_exceeded",
            "unknown_runtime_action",
            "no_checks_policy",
        ]
    ):
        category = "policy"
    elif any(x in blob for x in ["checks_failed", "test", "lint", "build", "compile", "validation"]):
        category = "code"
    elif any(x in blob for x in ["timeout", "docker", "stuck", "no_active_run", "conflict", "paused"]):
        category = "runtime"

    primary_reason = reasons[0] if reasons else status
    return {
        "category": category,
        "status": status,
        "reason": primary_reason,
        "signals": signals[:20],
    }


async def handle_backlog_list(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    if _require_project(manager, project_id) is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    status = (request.query.get("status") or "").strip().lower() or None
    if status and status not in {"todo", "in_progress", "done", "blocked"}:
        return web.json_response({"error": "invalid status filter"}, status=400)

    tasks = [t.__dict__.copy() for t in _get_store(request).list_tasks(project_id=project_id, status=status)]
    return web.json_response({"project_id": project_id, "tasks": tasks})


async def handle_backlog_intake_template(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "required_fields": ["title", "goal", "acceptance_criteria", "constraints", "delivery_mode"],
            "delivery_mode_options": sorted(INTAKE_DELIVERY_MODES),
            "example": {
                "title": "Fix POST->GET redirect downgrade in n8n API wrapper",
                "goal": "Implement redirect-safe request flow and validate behavior with regression checks.",
                "acceptance_criteria": [
                    "POST request method is preserved on 301/302 handling path",
                    "Regression test covers redirect-downgrade scenario",
                ],
                "constraints": [
                    "Container-first execution only",
                    "Do not add new runtime dependencies without approval",
                ],
                "delivery_mode": "patch_and_pr",
            },
        }
    )


async def handle_backlog_intake_validate(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        return web.json_response({"error": "json object expected"}, status=400)
    errors, normalized = _validate_intake_contract(body)
    if errors:
        return web.json_response(
            {
                "valid": False,
                "errors": errors,
                "hints": [
                    "Use /api/autonomous/backlog/intake/template for canonical payload shape.",
                    "Include specific outcome in goal and at least one explicit constraint.",
                ],
            },
            status=400,
        )
    return web.json_response({"valid": True, "normalized": normalized})


async def handle_backlog_create(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    project = _require_project(manager, project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        return web.json_response({"error": "json object expected"}, status=400)

    if _intake_contract_enabled(body.get("strict_intake")):
        intake_errors, _normalized = _validate_intake_contract(body)
        if intake_errors:
            return web.json_response(
                {
                    "error": "autonomous task intake contract validation failed",
                    "details": intake_errors,
                    "hint": "Use /api/autonomous/backlog/intake/template and retry with strict_intake=true payload.",
                },
                status=400,
            )

    title = str(body.get("title") or "").strip()
    goal = str(body.get("goal") or "").strip()
    if not title or not goal:
        return web.json_response({"error": "title and goal are required"}, status=400)

    criteria_raw = body.get("acceptance_criteria")
    if not isinstance(criteria_raw, list):
        return web.json_response({"error": "acceptance_criteria must be an array"}, status=400)
    criteria = [str(x).strip() for x in criteria_raw if str(x).strip()]
    if not criteria:
        return web.json_response({"error": "acceptance_criteria cannot be empty"}, status=400)

    try:
        priority = _validate_priority(str(body.get("priority") or "medium"))
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    try:
        required_checks = _normalize_string_array(body.get("required_checks"), field_name="required_checks")
        service_matrix = _normalize_string_array(body.get("service_matrix"), field_name="service_matrix")
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    workflow = str(body.get("workflow") or "").strip()
    requested_validation_mode = (
        str(body.get("validation_mode") or "").strip() if "validation_mode" in body else None
    )
    repository = str(body.get("repository") or project.get("repository") or "").strip()
    branch = str(body.get("branch") or _project_default_ref(project, include_env_default=False) or "").strip()
    try:
        validation_mode, validation_reason = _resolve_validation_contract(
            project=project,
            repository=repository,
            service_matrix=service_matrix,
            requested_mode=requested_validation_mode,
        )
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    task = _get_store(request).create_task(
        project_id=project_id,
        title=title,
        goal=goal,
        acceptance_criteria=criteria,
        priority=priority,
        repository=repository,
        branch=branch,
        required_checks=required_checks,
        workflow=workflow,
        service_matrix=service_matrix,
        validation_mode=validation_mode,
        validation_reason=validation_reason,
    )
    return web.json_response(task.__dict__.copy(), status=201)


async def handle_backlog_update(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    task_id = request.match_info["task_id"]
    project = _require_project(manager, project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    store = _get_store(request)
    task = store.get_task(task_id)
    if task is None or task.project_id != project_id:
        return web.json_response({"error": f"Task '{task_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    updates: dict[str, Any] = {}
    if "title" in body:
        updates["title"] = str(body.get("title") or "")
    if "goal" in body:
        updates["goal"] = str(body.get("goal") or "")
    if "acceptance_criteria" in body:
        if not isinstance(body.get("acceptance_criteria"), list):
            return web.json_response({"error": "acceptance_criteria must be an array"}, status=400)
        updates["acceptance_criteria"] = body.get("acceptance_criteria")
    if "status" in body:
        try:
            updates["status"] = _validate_task_status(str(body.get("status") or ""))
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
    if "priority" in body:
        try:
            updates["priority"] = _validate_priority(str(body.get("priority") or ""))
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
    if "repository" in body:
        updates["repository"] = str(body.get("repository") or "")
    if "branch" in body:
        updates["branch"] = str(body.get("branch") or "")
    if "required_checks" in body:
        try:
            updates["required_checks"] = _normalize_string_array(
                body.get("required_checks"),
                field_name="required_checks",
            )
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
    if "workflow" in body:
        updates["workflow"] = str(body.get("workflow") or "")
    if "service_matrix" in body:
        try:
            updates["service_matrix"] = _normalize_string_array(
                body.get("service_matrix"),
                field_name="service_matrix",
            )
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
    if "validation_mode" in body and body.get("validation_mode") is not None:
        updates["validation_mode"] = str(body.get("validation_mode") or "").strip()

    if (
        "validation_mode" in updates
        or "service_matrix" in updates
        or "repository" in updates
    ):
        merged_repository = str(updates.get("repository", task.repository) or "").strip()
        merged_service_matrix = [
            str(x).strip()
            for x in (
                updates.get("service_matrix")
                if isinstance(updates.get("service_matrix"), list)
                else getattr(task, "service_matrix", []) or []
            )
            if str(x).strip()
        ]
        requested_mode = str(updates.get("validation_mode") or "").strip() if "validation_mode" in updates else None
        try:
            validation_mode, validation_reason = _resolve_validation_contract(
                project=project,
                repository=merged_repository,
                service_matrix=merged_service_matrix,
                requested_mode=requested_mode,
            )
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
        updates["validation_mode"] = validation_mode
        updates["validation_reason"] = validation_reason

    updated = store.update_task(task_id, updates)
    if updated is None:
        return web.json_response({"error": f"Task '{task_id}' not found"}, status=404)
    return web.json_response(updated.__dict__.copy())


async def handle_pipeline_runs_list(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    if _require_project(manager, project_id) is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    runs = [r.__dict__.copy() for r in _get_store(request).list_runs(project_id=project_id)]
    return web.json_response({"project_id": project_id, "runs": runs})


async def handle_pipeline_run_create(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    project = _require_project(manager, project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    task_id = str(body.get("task_id") or "").strip()
    if not task_id:
        return web.json_response({"error": "task_id is required"}, status=400)

    store = _get_store(request)
    task = store.get_task(task_id)
    if task is None or task.project_id != project_id:
        return web.json_response({"error": f"Task '{task_id}' not found"}, status=404)

    auto_start = bool(body.get("auto_start", True))
    session_id = str(body.get("session_id") or "").strip()
    run, err_text, status = await _create_run_for_task(
        manager=manager,
        store=store,
        project_id=project_id,
        task=task,
        auto_start=auto_start,
        session_id=session_id,
    )
    if err_text:
        return web.json_response({"error": err_text}, status=status)
    return web.json_response(run.__dict__.copy(), status=201)


async def handle_pipeline_dispatch_next(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    project = _require_project(manager, project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    store = _get_store(request)
    active_run = _project_has_active_run(store, project_id)
    if active_run is not None:
        return web.json_response(
            {
                "error": "Active pipeline run already exists",
                "active_run_id": active_run.id,
                "status": active_run.status,
                "current_stage": active_run.current_stage,
            },
            status=409,
        )

    body = await request.json() if request.can_read_body else {}
    auto_start = bool(body.get("auto_start", True))
    session_id = str(body.get("session_id") or "").strip()

    todo_tasks = store.list_tasks(project_id=project_id, status="todo")
    task = _pick_next_task(todo_tasks)
    if task is None:
        return web.json_response({"error": "No todo tasks in backlog"}, status=404)

    run, err_text, status = await _create_run_for_task(
        manager=manager,
        store=store,
        project_id=project_id,
        task=task,
        auto_start=auto_start,
        session_id=session_id,
    )
    if err_text:
        return web.json_response({"error": err_text}, status=status)
    return web.json_response(
        {
            "project_id": project_id,
            "selected_task": task.__dict__.copy(),
            "run": run.__dict__.copy(),
            "selection": {"strategy": "priority_then_created_at"},
        },
        status=201,
    )


async def _loop_tick_project(
    *,
    manager: Any,
    store: AutonomousPipelineStore,
    project_id: str,
    project: dict[str, Any],
    body: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    auto_start = bool(body.get("auto_start", True))
    session_id = str(body.get("session_id") or "").strip()

    active_run = _project_has_active_run(store, project_id)
    if active_run is None:
        todo_tasks = store.list_tasks(project_id=project_id, status="todo")
        task = _pick_next_task(todo_tasks)
        if task is None:
            return {"action": "idle_no_todo_tasks", "project_id": project_id}, 200
        run, err_text, status = await _create_run_for_task(
            manager=manager,
            store=store,
            project_id=project_id,
            task=task,
            auto_start=auto_start,
            session_id=session_id,
        )
        if err_text:
            return {"error": err_text}, status
        return {
            "action": "dispatched_next_task",
            "project_id": project_id,
            "selected_task": task.__dict__.copy(),
            "run": run.__dict__.copy(),
        }, 201

    stage = active_run.current_stage
    if stage == "execution":
        guardrails = _run_guardrails(project)
        outcome = _resolve_execution_outcome(manager, active_run)
        outcome_status = str(outcome.get("status") or "unknown")
        if outcome_status in {"completed", "failed", "paused"}:
            result = "success" if outcome_status == "completed" else "failed"
            updated, err_text = _apply_stage_result(
                store=store,
                project=project,
                project_id=project_id,
                run=active_run,
                stage="execution",
                result=result,
                notes=f"Execution outcome from event log: {outcome_status}",
                output={"execution": outcome},
                summary=f"Execution stage resolved: {outcome_status}",
                pr_url=None,
                source="execution_event",
            )
            if err_text:
                err_status = 409 if "currently at stage" in err_text else 400
                return {"error": err_text}, err_status
            return {
                "action": "execution_stage_resolved",
                "project_id": project_id,
                "outcome": outcome,
                "run": updated.__dict__.copy(),
            }, 200
        if outcome_status == "running":
            session_id = str(outcome.get("session_id") or "").strip()
            execution_id = str(outcome.get("execution_id") or "").strip()
            worker_graph_id = str(outcome.get("worker_graph_id") or "").strip()
            if session_id and execution_id:
                tool_calls = _count_execution_tool_calls(
                    session_id,
                    execution_id,
                    worker_graph_id=worker_graph_id,
                )
                max_tool_calls = int(guardrails.get("max_tool_calls_execution_stage") or 150)
                if tool_calls > max_tool_calls:
                    stopped = _apply_guardrail_terminal_stop(
                        store=store,
                        run=active_run,
                        stage="execution",
                        stop_action=str(guardrails.get("stop_action") or "failed"),
                        reason="max_tool_calls_exceeded",
                        details={
                            "tool_calls": tool_calls,
                            "max_tool_calls": max_tool_calls,
                            "session_id": session_id,
                            "execution_id": execution_id,
                        },
                    )
                    if stopped is not None:
                        store.update_task(stopped.task_id, {"status": "blocked"})
                        return {
                            "action": "guardrail_stopped",
                            "project_id": project_id,
                            "reason": "max_tool_calls_exceeded",
                            "run": stopped.__dict__.copy(),
                        }, 200
            stage_states = dict(active_run.stage_states)
            stage_states["execution"] = "running"
            artifacts = dict(active_run.artifacts) if isinstance(active_run.artifacts, dict) else {}
            stages = dict(artifacts.get("stages") or {}) if isinstance(artifacts.get("stages"), dict) else {}
            execution_stage = (
                dict(stages.get("execution") or {}) if isinstance(stages.get("execution"), dict) else {}
            )
            execution_stage.update(
                {
                    "result": "running",
                    "timestamp": time.time(),
                    "output": {"execution": outcome},
                    "attempt": max(int(active_run.attempts.get("execution", 0) or 0), 1),
                    "source": "execution_event_poll",
                }
            )
            stages["execution"] = execution_stage
            artifacts["stages"] = stages
            touched = (
                store.update_run(
                    active_run.id,
                    {
                        "status": "in_progress",
                        "stage_states": stage_states,
                        "artifacts": artifacts,
                    },
                )
                or active_run
            )
            return {
                "action": "await_execution_stage_result",
                "project_id": project_id,
                "outcome": outcome,
                "run": touched.__dict__.copy(),
            }, 202
        return {
            "action": "await_execution_stage_result",
            "project_id": project_id,
            "outcome": outcome,
            "run": active_run.__dict__.copy(),
        }, 202
    if stage not in {"review", "validation"}:
        return {
            "action": "await_manual_stage_resolution",
            "project_id": project_id,
            "run": active_run.__dict__.copy(),
        }, 202

    task = store.get_task(active_run.task_id)
    report_current = active_run.artifacts.get("report", {}) if isinstance(active_run.artifacts, dict) else {}
    report_pr_url = ""
    if isinstance(report_current, dict):
        pr_obj = report_current.get("pr", {})
        if isinstance(pr_obj, dict):
            report_pr_url = str(pr_obj.get("url") or "").strip()

    repository, ref, pr_url = _resolve_github_inputs(
        project=project,
        task=task,
        body=body,
        report_pr_url=report_pr_url,
    )
    required_raw = body.get("required_checks")
    required_checks = (
        [str(x).strip() for x in required_raw if str(x).strip()]
        if isinstance(required_raw, list)
        else None
    )
    notes = str(body.get("notes") or "").strip()
    summary = str(body.get("summary") or "").strip()

    token = (
        os.environ.get("GITHUB_TOKEN", "").strip()
        or os.environ.get("GH_TOKEN", "").strip()
        or os.environ.get("GITHUB_PAT", "").strip()
    )
    if not token:
        if _auto_next_fallback_mode() == "manual_pending":
            deferred = _append_run_event(
                store=store,
                run=active_run,
                event_type="auto_next_deferred",
                data={"reason": "missing_github_token", "stage": stage, "source": "loop_tick"},
            ) or active_run
            return {
                "action": "manual_evaluate_required",
                "deferred": True,
                "reason": "missing_github_token",
                "run": deferred.__dict__.copy(),
            }, 202
        return {"error": "GITHUB_TOKEN (or GH_TOKEN/GITHUB_PAT) is required"}, 400

    updated, err_text, status = _evaluate_github_for_run(
        store=store,
        project=project,
        project_id=project_id,
        run=active_run,
        stage=stage,
        repository=repository,
        ref=ref,
        pr_url=pr_url,
        required_checks=required_checks,
        notes=notes,
        summary=summary,
        token=token,
        source="loop_tick",
    )
    if err_text:
        if status == 202:
            deferred = _append_run_event(
                store=store,
                run=active_run,
                event_type="auto_next_deferred",
                data={"reason": err_text, "stage": stage, "status": status, "source": "loop_tick"},
            ) or active_run
            return {
                "action": "manual_evaluate_required",
                "deferred": True,
                "reason": err_text,
                "status": status,
                "run": deferred.__dict__.copy(),
            }, 202
        if _auto_next_fallback_mode() == "manual_pending":
            deferred = _append_run_event(
                store=store,
                run=active_run,
                event_type="auto_next_deferred",
                data={"reason": err_text, "stage": stage, "status": status, "source": "loop_tick"},
            ) or active_run
            return {
                "action": "manual_evaluate_required",
                "deferred": True,
                "reason": err_text,
                "status": status,
                "run": deferred.__dict__.copy(),
            }, 202
        return {"error": err_text}, status
    return {
        "action": "advanced_with_github_checks",
        "project_id": project_id,
        "run": updated.__dict__.copy(),
    }, 200


async def handle_pipeline_loop_tick(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    project = _require_project(manager, project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    store = _get_store(request)
    body = await request.json() if request.can_read_body else {}
    payload, status = await _loop_tick_project(
        manager=manager,
        store=store,
        project_id=project_id,
        project=project,
        body=body if isinstance(body, dict) else {},
    )
    return web.json_response(payload, status=status)


async def handle_pipeline_loop_tick_all(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    store = _get_store(request)
    body = await request.json() if request.can_read_body else {}
    req = body if isinstance(body, dict) else {}

    requested_ids = req.get("project_ids")
    if requested_ids is not None and not isinstance(requested_ids, list):
        return web.json_response({"error": "project_ids must be an array when provided"}, status=400)
    targets = [str(x).strip() for x in (requested_ids or []) if str(x).strip()]
    if not targets:
        targets = [str(p.get("id") or "").strip() for p in manager.list_projects() if str(p.get("id") or "").strip()]

    session_by_project_raw = req.get("session_id_by_project")
    session_by_project: dict[str, str] = {}
    if isinstance(session_by_project_raw, dict):
        for k, v in session_by_project_raw.items():
            pk = str(k).strip()
            sv = str(v).strip()
            if pk and sv:
                session_by_project[pk] = sv

    results: list[dict[str, Any]] = []
    for project_id in targets:
        project = _require_project(manager, project_id)
        if project is None:
            results.append({"project_id": project_id, "status": 404, "error": f"Project '{project_id}' not found"})
            continue
        child_body = dict(req)
        if project_id in session_by_project:
            child_body["session_id"] = session_by_project[project_id]
        payload, status = await _loop_tick_project(
            manager=manager,
            store=store,
            project_id=project_id,
            project=project,
            body=child_body,
        )
        row = {"project_id": project_id, "status": status}
        row.update(payload)
        results.append(row)

    ok = sum(1 for r in results if int(r.get("status", 500)) < 400)
    failed = len(results) - ok
    return web.json_response(
        {
            "status": "ok" if failed == 0 else "partial",
            "summary": {"projects_total": len(results), "ok": ok, "failed": failed},
            "results": results,
        }
    )


def _cycle_should_continue(action: str) -> bool:
    return action in {"dispatched_next_task", "execution_stage_resolved", "advanced_with_github_checks"}


def _extract_run_metrics(run_payload: Any) -> dict[str, Any]:
    if not isinstance(run_payload, dict):
        return {}
    run_id = str(run_payload.get("id") or "").strip()
    run_status = str(run_payload.get("status") or "").strip()
    current_stage = str(run_payload.get("current_stage") or "").strip()
    terminal = run_status in {"completed", "failed", "escalated"}

    pr_ready = False
    pr_url: str | None = None
    artifacts = run_payload.get("artifacts")
    if isinstance(artifacts, dict):
        report = artifacts.get("report")
        if isinstance(report, dict):
            pr = report.get("pr")
            if isinstance(pr, dict):
                pr_ready = bool(pr.get("ready"))
                url = str(pr.get("url") or "").strip()
                pr_url = url or None

    out: dict[str, Any] = {
        "run_id": run_id or None,
        "run_status": run_status or None,
        "current_stage": current_stage or None,
        "terminal": terminal,
    }
    if terminal:
        out["terminal_status"] = run_status
    if pr_url is not None:
        out["pr_url"] = pr_url
    out["pr_ready"] = pr_ready
    return out


def _classify_cycle_outcome(row: dict[str, Any]) -> str:
    if str(row.get("error") or "").strip():
        return "error"
    terminal = bool(row.get("terminal"))
    if terminal:
        status = str(row.get("terminal_status") or "").strip().lower()
        if status in {"completed", "failed", "escalated"}:
            return status
        return "terminal_unknown"
    action = str(row.get("action") or "").strip().lower()
    if action == "manual_evaluate_required":
        return "manual_deferred"
    if action == "idle_no_todo_tasks":
        return "idle"
    if action in {"await_execution_stage_result", "await_manual_stage_resolution"}:
        return "in_progress"
    if action:
        return f"action:{action}"
    return "unknown"


async def handle_pipeline_loop_run_cycle(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    store = _get_store(request)
    body = await request.json() if request.can_read_body else {}
    req = body if isinstance(body, dict) else {}

    requested_ids = req.get("project_ids")
    if requested_ids is not None and not isinstance(requested_ids, list):
        return web.json_response({"error": "project_ids must be an array when provided"}, status=400)

    max_steps_raw = req.get("max_steps_per_project", 3)
    try:
        max_steps = int(max_steps_raw)
    except (TypeError, ValueError):
        return web.json_response({"error": "max_steps_per_project must be an integer"}, status=400)
    if max_steps < 1 or max_steps > 20:
        return web.json_response({"error": "max_steps_per_project must be between 1 and 20"}, status=400)

    targets = [str(x).strip() for x in (requested_ids or []) if str(x).strip()]
    if not targets:
        targets = [str(p.get("id") or "").strip() for p in manager.list_projects() if str(p.get("id") or "").strip()]

    session_by_project_raw = req.get("session_id_by_project")
    session_by_project: dict[str, str] = {}
    if isinstance(session_by_project_raw, dict):
        for k, v in session_by_project_raw.items():
            pk = str(k).strip()
            sv = str(v).strip()
            if pk and sv:
                session_by_project[pk] = sv

    results: list[dict[str, Any]] = []
    for project_id in targets:
        project = _require_project(manager, project_id)
        if project is None:
            results.append(
                {
                    "project_id": project_id,
                    "status": 404,
                    "error": f"Project '{project_id}' not found",
                    "steps_executed": 0,
                    "steps": [],
                }
            )
            continue

        child_body = dict(req)
        if project_id in session_by_project:
            child_body["session_id"] = session_by_project[project_id]

        steps: list[dict[str, Any]] = []
        final_payload: dict[str, Any] = {}
        final_status = 200
        terminal_metrics: dict[str, Any] = {}
        last_run_metrics: dict[str, Any] = {}
        for _ in range(max_steps):
            payload, status = await _loop_tick_project(
                manager=manager,
                store=store,
                project_id=project_id,
                project=project,
                body=child_body,
            )
            final_payload = payload
            final_status = status
            action = str(payload.get("action") or "")
            run_metrics = _extract_run_metrics(payload.get("run"))
            if run_metrics:
                last_run_metrics = run_metrics
                if bool(run_metrics.get("terminal")):
                    terminal_metrics = run_metrics
            steps.append({"status": status, "action": action, "error": payload.get("error"), "reason": payload.get("reason")})
            if status >= 400 or not _cycle_should_continue(action):
                break

        row = {
            "project_id": project_id,
            "status": final_status,
            "steps_executed": len(steps),
            "steps": steps,
            "terminal": bool(terminal_metrics.get("terminal")),
        }
        if terminal_metrics:
            row["terminal_status"] = terminal_metrics.get("terminal_status")
            row["terminal_run_id"] = terminal_metrics.get("run_id")
            row["pr_ready"] = bool(terminal_metrics.get("pr_ready"))
            if terminal_metrics.get("pr_url") is not None:
                row["pr_url"] = terminal_metrics.get("pr_url")
        elif last_run_metrics:
            row["run_id"] = last_run_metrics.get("run_id")
            row["run_status"] = last_run_metrics.get("run_status")
            row["current_stage"] = last_run_metrics.get("current_stage")
            row["pr_ready"] = bool(last_run_metrics.get("pr_ready"))
        row.update(final_payload)
        results.append(row)

    ok = sum(1 for r in results if int(r.get("status", 500)) < 400)
    failed = len(results) - ok
    outcomes: dict[str, int] = {}
    for row in results:
        outcome = _classify_cycle_outcome(row)
        row["outcome"] = outcome
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    return web.json_response(
        {
            "status": "ok" if failed == 0 else "partial",
            "summary": {
                "projects_total": len(results),
                "ok": ok,
                "failed": failed,
                "max_steps_per_project": max_steps,
                "outcomes": outcomes,
            },
            "results": results,
        }
    )


def _compact_cycle_report(cycle_payload: dict[str, Any]) -> dict[str, Any]:
    results = cycle_payload.get("results", [])
    if not isinstance(results, list):
        results = []
    summary = cycle_payload.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    projects: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        run = row.get("run")
        run_report = {}
        if isinstance(run, dict):
            artifacts = run.get("artifacts")
            if isinstance(artifacts, dict):
                report = artifacts.get("report")
                if isinstance(report, dict):
                    run_report = report
        row_risks = run_report.get("risks", [])
        if isinstance(row_risks, list):
            for r in row_risks:
                if isinstance(r, dict):
                    risks.append(r)
        projects.append(
            {
                "project_id": row.get("project_id"),
                "outcome": row.get("outcome"),
                "status": row.get("status"),
                "action": row.get("action"),
                "terminal": bool(row.get("terminal")),
                "terminal_status": row.get("terminal_status"),
                "terminal_run_id": row.get("terminal_run_id"),
                "pr_ready": bool(row.get("pr_ready")),
                "pr_url": row.get("pr_url"),
                "steps_executed": row.get("steps_executed"),
                "error": row.get("error"),
                "reason": row.get("reason"),
                "risk_count": len(row_risks) if isinstance(row_risks, list) else 0,
            }
        )

    highlights = {
        "terminal_ready_projects": [p["project_id"] for p in projects if p.get("terminal") and p.get("pr_ready")],
        "blocked_projects": [p["project_id"] for p in projects if p.get("terminal_status") in {"failed", "escalated"}],
        "manual_deferred_projects": [p["project_id"] for p in projects if p.get("outcome") == "manual_deferred"],
        "top_risks": risks[:10],
    }

    return {
        "status": cycle_payload.get("status"),
        "timestamp": time.time(),
        "summary": {
            "projects_total": summary.get("projects_total"),
            "ok": summary.get("ok"),
            "failed": summary.get("failed"),
            "max_steps_per_project": summary.get("max_steps_per_project"),
            "outcomes": summary.get("outcomes", {}),
            "terminal_ready": len(highlights["terminal_ready_projects"]),
            "blocked": len(highlights["blocked_projects"]),
            "manual_deferred": len(highlights["manual_deferred_projects"]),
            "risk_items": len(risks),
        },
        "projects": projects,
        "highlights": highlights,
    }


async def handle_pipeline_loop_run_cycle_report(request: web.Request) -> web.Response:
    cycle_resp = await handle_pipeline_loop_run_cycle(request)
    if cycle_resp.status >= 400:
        return cycle_resp
    payload = getattr(cycle_resp, "_body", None)
    if not payload:
        return web.json_response({"error": "failed to render cycle report"}, status=500)
    try:
        cycle_payload = json.loads(payload.decode("utf-8"))
    except Exception:
        return web.json_response({"error": "failed to parse cycle payload"}, status=500)
    return web.json_response(_compact_cycle_report(cycle_payload), status=200)


async def handle_pipeline_run_get(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    run_id = request.match_info["run_id"]
    if _require_project(manager, project_id) is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    run = _get_store(request).get_run(run_id)
    if run is None or run.project_id != project_id:
        return web.json_response({"error": f"Run '{run_id}' not found"}, status=404)
    return web.json_response(run.__dict__.copy())


async def handle_pipeline_run_report(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    run_id = request.match_info["run_id"]
    if _require_project(manager, project_id) is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    run = _get_store(request).get_run(run_id)
    if run is None or run.project_id != project_id:
        return web.json_response({"error": f"Run '{run_id}' not found"}, status=404)
    report = run.artifacts.get("report") if isinstance(run.artifacts, dict) else {}
    stages = run.artifacts.get("stages") if isinstance(run.artifacts, dict) else {}
    failure_taxonomy = _classify_terminal_failure(run)
    timeline = _build_run_timeline(run)
    return web.json_response(
        {
            "run_id": run.id,
            "project_id": run.project_id,
            "task_id": run.task_id,
            "status": run.status,
            "current_stage": run.current_stage,
            "attempts": run.attempts,
            "report": report if isinstance(report, dict) else {},
            "stages": stages if isinstance(stages, dict) else {},
            "failure_taxonomy": failure_taxonomy or {},
            "timeline": timeline,
        }
    )


async def handle_pipeline_run_advance(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    run_id = request.match_info["run_id"]
    project = _require_project(manager, project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    store = _get_store(request)
    run = store.get_run(run_id)
    if run is None or run.project_id != project_id:
        return web.json_response({"error": f"Run '{run_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    stage = str(body.get("stage") or run.current_stage).strip().lower()
    result = str(body.get("result") or "success").strip().lower()
    notes = str(body.get("notes") or "").strip()
    output = body.get("output")
    summary = str(body.get("summary") or "").strip()
    pr_url = str(body.get("pr_url") or "").strip() or None

    updated, err_text = _apply_stage_result(
        store=store,
        project=project,
        project_id=project_id,
        run=run,
        stage=stage,
        result=result,
        notes=notes,
        output=output,
        summary=summary,
        pr_url=pr_url,
        source="manual",
    )
    if err_text:
        status = 409 if "currently at stage" in err_text else 400
        return web.json_response({"error": err_text}, status=status)
    return web.json_response(updated.__dict__.copy())


async def handle_pipeline_run_evaluate(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    run_id = request.match_info["run_id"]
    project = _require_project(manager, project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    store = _get_store(request)
    run = store.get_run(run_id)
    if run is None or run.project_id != project_id:
        return web.json_response({"error": f"Run '{run_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    stage = str(body.get("stage") or run.current_stage).strip().lower()
    source = str(body.get("source") or "review_checks").strip() or "review_checks"
    notes = str(body.get("notes") or "").strip()
    summary = str(body.get("summary") or "").strip()
    pr_url = str(body.get("pr_url") or "").strip() or None
    try:
        checks = _normalize_checks(body.get("checks"))
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    if not checks:
        return web.json_response({"error": "checks cannot be empty"}, status=400)
    checks_sum = _checks_summary(checks)
    result = "success" if checks_sum["all_passed"] else "failed"

    updated, err_text = _apply_stage_result(
        store=store,
        project=project,
        project_id=project_id,
        run=run,
        stage=stage,
        result=result,
        notes=notes,
        output={"checks_summary": checks_sum},
        summary=summary,
        pr_url=pr_url,
        source=source,
        checks=checks,
    )
    if err_text:
        status = 409 if "currently at stage" in err_text else 400
        return web.json_response({"error": err_text}, status=status)
    return web.json_response(updated.__dict__.copy())


async def handle_pipeline_run_evaluate_github(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    run_id = request.match_info["run_id"]
    project = _require_project(manager, project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    store = _get_store(request)
    run = store.get_run(run_id)
    if run is None or run.project_id != project_id:
        return web.json_response({"error": f"Run '{run_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    stage = str(body.get("stage") or run.current_stage).strip().lower()
    task = store.get_task(run.task_id)
    report_current = run.artifacts.get("report", {}) if isinstance(run.artifacts, dict) else {}
    report_pr_url = ""
    if isinstance(report_current, dict):
        pr_obj = report_current.get("pr", {})
        if isinstance(pr_obj, dict):
            report_pr_url = str(pr_obj.get("url") or "").strip()

    repository, ref, pr_url = _resolve_github_inputs(
        project=project,
        task=task,
        body=body,
        report_pr_url=report_pr_url,
    )
    required_raw = body.get("required_checks")
    required_checks = (
        [str(x).strip() for x in required_raw if str(x).strip()]
        if isinstance(required_raw, list)
        else None
    )
    notes = str(body.get("notes") or "").strip()
    summary = str(body.get("summary") or "").strip()
    post_review_summary = _parse_bool_param(body.get("post_review_summary"), default=False)
    review_summary_comment = str(body.get("review_summary_comment") or "").strip()
    try:
        pr_number = _parse_optional_positive_int(body.get("pr_number"), field_name="pr_number")
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    token = (
        os.environ.get("GITHUB_TOKEN", "").strip()
        or os.environ.get("GH_TOKEN", "").strip()
        or os.environ.get("GITHUB_PAT", "").strip()
    )
    if not token:
        return web.json_response({"error": "GITHUB_TOKEN (or GH_TOKEN/GITHUB_PAT) is required"}, status=400)
    updated, err_text, status = _evaluate_github_for_run(
        store=store,
        project=project,
        project_id=project_id,
        run=run,
        stage=stage,
        repository=repository,
        ref=ref,
        pr_url=pr_url,
        required_checks=required_checks,
        notes=notes,
        summary=summary,
        token=token,
        source="github_checks",
        pr_number=pr_number,
        post_review_summary=post_review_summary,
        review_summary_comment=review_summary_comment,
    )
    if err_text:
        if status == 202:
            deferred = _append_run_event(
                store=store,
                run=run,
                event_type="auto_next_deferred",
                data={"reason": err_text, "stage": stage, "status": status, "source": "github_checks"},
            ) or run
            return web.json_response(
                {
                    "deferred": True,
                    "reason": err_text,
                    "status": status,
                    "current_stage": deferred.current_stage,
                    "action": "manual_evaluate_required",
                },
                status=202,
            )
        return web.json_response({"error": err_text}, status=status)
    return web.json_response(updated.__dict__.copy())


async def handle_pipeline_run_auto_next(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    run_id = request.match_info["run_id"]
    project = _require_project(manager, project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    store = _get_store(request)
    run = store.get_run(run_id)
    if run is None or run.project_id != project_id:
        return web.json_response({"error": f"Run '{run_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    stage = run.current_stage
    if stage not in {"review", "validation"}:
        return web.json_response(
            {
                "error": f"auto-next supports review/validation only (current: {stage})",
                "current_stage": stage,
            },
            status=409,
        )

    task = store.get_task(run.task_id)
    report_current = run.artifacts.get("report", {}) if isinstance(run.artifacts, dict) else {}
    report_pr_url = ""
    if isinstance(report_current, dict):
        pr_obj = report_current.get("pr", {})
        if isinstance(pr_obj, dict):
            report_pr_url = str(pr_obj.get("url") or "").strip()

    repository, ref, pr_url = _resolve_github_inputs(
        project=project,
        task=task,
        body=body,
        report_pr_url=report_pr_url,
    )
    required_raw = body.get("required_checks")
    required_checks = (
        [str(x).strip() for x in required_raw if str(x).strip()]
        if isinstance(required_raw, list)
        else None
    )
    notes = str(body.get("notes") or "").strip()
    summary = str(body.get("summary") or "").strip()
    post_review_summary = _parse_bool_param(body.get("post_review_summary"), default=False)
    review_summary_comment = str(body.get("review_summary_comment") or "").strip()
    try:
        pr_number = _parse_optional_positive_int(body.get("pr_number"), field_name="pr_number")
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    token = (
        os.environ.get("GITHUB_TOKEN", "").strip()
        or os.environ.get("GH_TOKEN", "").strip()
        or os.environ.get("GITHUB_PAT", "").strip()
    )
    if not token:
        mode = _auto_next_fallback_mode()
        reason = "missing_github_token"
        if mode == "manual_pending":
            updated = _append_run_event(
                store=store,
                run=run,
                event_type="auto_next_deferred",
                data={"reason": reason, "stage": stage},
            ) or run
            return web.json_response(
                {
                    "deferred": True,
                    "reason": reason,
                    "current_stage": updated.current_stage,
                    "action": "manual_evaluate_required",
                },
                status=202,
            )
        return web.json_response({"error": "GITHUB_TOKEN (or GH_TOKEN/GITHUB_PAT) is required"}, status=400)

    updated, err_text, status = _evaluate_github_for_run(
        store=store,
        project=project,
        project_id=project_id,
        run=run,
        stage=stage,
        repository=repository,
        ref=ref,
        pr_url=pr_url,
        required_checks=required_checks,
        notes=notes,
        summary=summary,
        token=token,
        source="auto_next",
        pr_number=pr_number,
        post_review_summary=post_review_summary,
        review_summary_comment=review_summary_comment,
    )
    if err_text:
        if status == 202:
            deferred = _append_run_event(
                store=store,
                run=run,
                event_type="auto_next_deferred",
                data={"reason": err_text, "stage": stage, "status": status},
            ) or run
            return web.json_response(
                {
                    "deferred": True,
                    "reason": err_text,
                    "status": status,
                    "current_stage": deferred.current_stage,
                    "action": "manual_evaluate_required",
                },
                status=202,
            )
        if _auto_next_fallback_mode() == "manual_pending":
            deferred = _append_run_event(
                store=store,
                run=run,
                event_type="auto_next_deferred",
                data={"reason": err_text, "stage": stage, "status": status},
            ) or run
            return web.json_response(
                {
                    "deferred": True,
                    "reason": err_text,
                    "status": status,
                    "current_stage": deferred.current_stage,
                    "action": "manual_evaluate_required",
                },
                status=202,
            )
        return web.json_response({"error": err_text}, status=status)
    return web.json_response(updated.__dict__.copy())


async def _run_until_terminal(
    *,
    manager: Any,
    store: AutonomousPipelineStore,
    project_id: str,
    project: dict[str, Any],
    run_id: str,
    req: dict[str, Any],
    max_steps: int,
) -> tuple[dict[str, Any], int]:
    run = store.get_run(run_id)
    if run is None or run.project_id != project_id:
        return {"error": f"Run '{run_id}' not found"}, 404

    guardrails = _run_guardrails(project)
    max_run_seconds = int(guardrails.get("max_run_seconds") or 1800)
    max_loop_ticks = int(guardrails.get("max_loop_ticks_per_run") or 24)
    stop_action = str(guardrails.get("stop_action") or "failed")
    fail_on_unknown_action = bool(guardrails.get("fail_on_unknown_action"))
    effective_max_steps = min(max_steps, max_loop_ticks)

    steps: list[dict[str, Any]] = []
    final_run = run
    terminal = final_run.status in {"completed", "failed", "escalated"}
    action = "already_terminal" if terminal else "run_started"

    for _ in range(effective_max_steps):
        final_run = store.get_run(run_id) or final_run
        if final_run.status in {"completed", "failed", "escalated"}:
            terminal = True
            action = "terminal"
            break
        elapsed_seconds = max(0.0, float(time.time() - float(final_run.started_at or 0.0)))
        if elapsed_seconds > float(max_run_seconds):
            stopped = _apply_guardrail_terminal_stop(
                store=store,
                run=final_run,
                stage=str(final_run.current_stage or "execution"),
                stop_action=stop_action,
                reason="max_run_seconds_exceeded",
                details={
                    "elapsed_seconds": elapsed_seconds,
                    "max_run_seconds": max_run_seconds,
                },
            )
            if stopped is not None:
                store.update_task(stopped.task_id, {"status": "blocked"})
                final_run = stopped
                terminal = True
                action = "guardrail_stopped"
                break

        active_run = _project_has_active_run(store, project_id)
        if active_run is None:
            action = "no_active_run"
            break
        if active_run.id != run_id:
            return (
                {
                    "error": "Another active run is currently owning project execution",
                    "active_run_id": active_run.id,
                    "requested_run_id": run_id,
                    "project_id": project_id,
                },
                409,
            )

        tick_payload, tick_status = await _loop_tick_project(
            manager=manager,
            store=store,
            project_id=project_id,
            project=project,
            body=req,
        )
        row: dict[str, Any] = {"status": tick_status}
        row.update(tick_payload)
        steps.append(row)
        action = str(tick_payload.get("action") or action)
        final_run = store.get_run(run_id) or final_run
        if final_run.status in {"completed", "failed", "escalated"}:
            terminal = True
            action = "terminal"
            break
        known_non_terminal_actions = {
            "dispatched_next_task",
            "execution_stage_resolved",
            "advanced_with_github_checks",
            "await_execution_stage_result",
            "await_manual_stage_resolution",
            "manual_evaluate_required",
            "idle_no_todo_tasks",
            "no_active_run",
        }
        if fail_on_unknown_action and action and action not in known_non_terminal_actions:
            stopped = _apply_guardrail_terminal_stop(
                store=store,
                run=final_run,
                stage=str(final_run.current_stage or "execution"),
                stop_action=stop_action,
                reason="unknown_runtime_action",
                details={"action": action},
            )
            if stopped is not None:
                store.update_task(stopped.task_id, {"status": "blocked"})
                final_run = stopped
                terminal = True
                action = "guardrail_stopped"
                break
        if not _cycle_should_continue(action):
            break

    return (
        {
            "project_id": project_id,
            "run_id": run_id,
            "terminal": terminal,
            "terminal_status": final_run.status if terminal else None,
            "current_stage": final_run.current_stage,
            "status": final_run.status,
            "steps_executed": len(steps),
            "max_steps": max_steps,
            "effective_max_steps": effective_max_steps,
            "action": action,
            "steps": steps,
            "run": final_run.__dict__.copy(),
        },
        200,
    )


async def handle_pipeline_run_until_terminal(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    run_id = request.match_info["run_id"]
    project = _require_project(manager, project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    store = _get_store(request)
    run = store.get_run(run_id)
    if run is None or run.project_id != project_id:
        return web.json_response({"error": f"Run '{run_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    req = body if isinstance(body, dict) else {}
    max_steps_raw = req.get("max_steps", 8)
    try:
        max_steps = int(max_steps_raw)
    except Exception:
        return web.json_response({"error": "max_steps must be an integer"}, status=400)
    if max_steps < 1 or max_steps > 100:
        return web.json_response({"error": "max_steps must be between 1 and 100"}, status=400)

    payload, status = await _run_until_terminal(
        manager=manager,
        store=store,
        project_id=project_id,
        project=project,
        run_id=run_id,
        req=req,
        max_steps=max_steps,
    )
    return web.json_response(payload, status=status)


async def handle_pipeline_execute_next(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    project_id = request.match_info["project_id"]
    project = _require_project(manager, project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    store = _get_store(request)
    body = await request.json() if request.can_read_body else {}
    req = body if isinstance(body, dict) else {}
    max_steps_raw = req.get("max_steps", 8)
    try:
        max_steps = int(max_steps_raw)
    except Exception:
        return web.json_response({"error": "max_steps must be an integer"}, status=400)
    if max_steps < 1 or max_steps > 100:
        return web.json_response({"error": "max_steps must be between 1 and 100"}, status=400)

    active_run = _project_has_active_run(store, project_id)
    run_id: str | None = None
    selected_task: dict[str, Any] | None = None
    if active_run is None:
        todo_tasks = store.list_tasks(project_id=project_id, status="todo")
        task = _pick_next_task(todo_tasks)
        if task is None:
            return web.json_response({"error": "No todo tasks in backlog"}, status=404)
        run, err_text, status = await _create_run_for_task(
            manager=manager,
            store=store,
            project_id=project_id,
            task=task,
            auto_start=bool(req.get("auto_start", True)),
            session_id=str(req.get("session_id") or "").strip(),
        )
        if err_text:
            return web.json_response({"error": err_text}, status=status)
        run_id = run.id if run is not None else None
        selected_task = task.__dict__.copy()
    else:
        run_id = active_run.id

    if not run_id:
        return web.json_response({"error": "Failed to select run"}, status=500)

    payload, status = await _run_until_terminal(
        manager=manager,
        store=store,
        project_id=project_id,
        project=project,
        run_id=run_id,
        req=req,
        max_steps=max_steps,
    )
    if selected_task is not None and isinstance(payload, dict):
        payload["selected_task"] = selected_task
    return web.json_response(payload, status=status)


async def handle_autonomous_ops_status(request: web.Request) -> web.Response:
    manager = request.app[APP_KEY_MANAGER]
    store = _get_store(request)
    project_filter = request.query.get("project_id", "").strip()
    include_runs = request.query.get("include_runs", "").strip().lower() in {"1", "true", "yes"}
    include_orphaned = _parse_bool_param(request.query.get("include_orphaned"), default=False)

    tasks = store.list_all_tasks()
    runs = store.list_all_runs()
    projects = manager.list_projects() if hasattr(manager, "list_projects") else []
    active_project_ids = {str(item.get("id", "")).strip() for item in projects if str(item.get("id", "")).strip()}
    orphaned_tasks_total = sum(1 for t in tasks if t.project_id not in active_project_ids)
    orphaned_runs_total = sum(1 for r in runs if r.project_id not in active_project_ids)
    if project_filter:
        tasks = [t for t in tasks if t.project_id == project_filter]
        runs = [r for r in runs if r.project_id == project_filter]
        projects = [p for p in projects if str(p.get("id", "")) == project_filter]
    elif not include_orphaned:
        tasks = [t for t in tasks if t.project_id in active_project_ids]
        runs = [r for r in runs if r.project_id in active_project_ids]
    now_ts = time.time()
    stuck_threshold = _stuck_run_threshold_seconds()
    no_progress_threshold = _no_progress_threshold_seconds()
    loop_stale_threshold = _loop_stale_threshold_seconds()
    docker_lane = _docker_lane_health()
    guardrail_stops_total = 0
    guardrail_stops_by_reason: dict[str, int] = {}
    failure_taxonomy: dict[str, int] = {}
    terminal_failures_total = 0

    per_project: dict[str, dict[str, Any]] = {}
    for t in tasks:
        bucket = per_project.setdefault(
            t.project_id,
            {
                "task_status": {},
                "run_status": {},
                "current_stage": {},
                "updated_at": 0.0,
                "stuck_runs": 0,
                "max_stuck_for_seconds": 0.0,
                "active_runs": 0,
                "max_no_progress_seconds": 0.0,
                "guardrail_stops": 0,
                "guardrail_stop_reasons": {},
                "terminal_failures": 0,
                "failure_taxonomy": {},
            },
        )
        ts = bucket["task_status"]
        ts[t.status] = ts.get(t.status, 0) + 1
        bucket["updated_at"] = max(float(bucket["updated_at"]), float(t.updated_at))

    stuck_runs: list[dict[str, Any]] = []
    active_runs_details: list[dict[str, Any]] = []
    for r in runs:
        bucket = per_project.setdefault(
            r.project_id,
            {
                "task_status": {},
                "run_status": {},
                "current_stage": {},
                "updated_at": 0.0,
                "stuck_runs": 0,
                "max_stuck_for_seconds": 0.0,
                "active_runs": 0,
                "max_no_progress_seconds": 0.0,
                "guardrail_stops": 0,
                "guardrail_stop_reasons": {},
                "terminal_failures": 0,
                "failure_taxonomy": {},
            },
        )
        rs = bucket["run_status"]
        cs = bucket["current_stage"]
        rs[r.status] = rs.get(r.status, 0) + 1
        cs[r.current_stage] = cs.get(r.current_stage, 0) + 1
        bucket["updated_at"] = max(float(bucket["updated_at"]), float(r.updated_at))
        artifacts = r.artifacts if isinstance(r.artifacts, dict) else {}
        report = artifacts.get("report") if isinstance(artifacts.get("report"), dict) else {}
        guardrail_obj = report.get("guardrail_stop") if isinstance(report, dict) else {}
        if isinstance(guardrail_obj, dict):
            reason = str(guardrail_obj.get("reason") or "").strip() or "unknown"
            guardrail_stops_total += 1
            guardrail_stops_by_reason[reason] = int(guardrail_stops_by_reason.get(reason, 0)) + 1
            bucket["guardrail_stops"] = int(bucket.get("guardrail_stops", 0)) + 1
            reason_counts = bucket.get("guardrail_stop_reasons")
            if not isinstance(reason_counts, dict):
                reason_counts = {}
            reason_counts[reason] = int(reason_counts.get(reason, 0)) + 1
            bucket["guardrail_stop_reasons"] = reason_counts

        terminal_failure = _classify_terminal_failure(r)
        if isinstance(terminal_failure, dict):
            category = str(terminal_failure.get("category") or "").strip().lower() or "runtime"
            terminal_failures_total += 1
            failure_taxonomy[category] = int(failure_taxonomy.get(category, 0)) + 1
            bucket["terminal_failures"] = int(bucket.get("terminal_failures", 0)) + 1
            per_project_tax = bucket.get("failure_taxonomy")
            if not isinstance(per_project_tax, dict):
                per_project_tax = {}
            per_project_tax[category] = int(per_project_tax.get(category, 0)) + 1
            bucket["failure_taxonomy"] = per_project_tax
        if r.status in {"queued", "in_progress"}:
            bucket["active_runs"] = int(bucket.get("active_runs", 0)) + 1
            stuck_for = max(0.0, float(now_ts) - float(r.updated_at))
            bucket["max_no_progress_seconds"] = max(float(bucket.get("max_no_progress_seconds", 0.0)), stuck_for)
            if include_runs:
                active_runs_details.append(
                    {
                        "project_id": r.project_id,
                        "run_id": r.id,
                        "status": r.status,
                        "current_stage": r.current_stage,
                        "updated_at": r.updated_at,
                        "no_progress_seconds": stuck_for,
                        "guardrail_stop_reason": str(guardrail_obj.get("reason") or "").strip()
                        if isinstance(guardrail_obj, dict)
                        else None,
                        "terminal_failure_category": str(terminal_failure.get("category") or "").strip()
                        if isinstance(terminal_failure, dict)
                        else None,
                    }
                )
            if stuck_for >= float(stuck_threshold):
                bucket["stuck_runs"] = int(bucket.get("stuck_runs", 0)) + 1
                bucket["max_stuck_for_seconds"] = max(float(bucket.get("max_stuck_for_seconds", 0.0)), stuck_for)
                stuck_runs.append(
                    {
                        "project_id": r.project_id,
                        "run_id": r.id,
                        "status": r.status,
                        "current_stage": r.current_stage,
                        "updated_at": r.updated_at,
                        "stuck_for_seconds": stuck_for,
                    }
                )

    stuck_runs.sort(key=lambda item: float(item.get("stuck_for_seconds", 0.0)), reverse=True)
    active_runs_details.sort(key=lambda item: float(item.get("no_progress_seconds", 0.0)), reverse=True)
    no_progress_projects: list[dict[str, Any]] = []
    for project_id, bucket in per_project.items():
        active_runs = int(bucket.get("active_runs", 0))
        max_no_progress_seconds = float(bucket.get("max_no_progress_seconds", 0.0))
        if active_runs <= 0:
            continue
        if max_no_progress_seconds < float(no_progress_threshold):
            continue
        no_progress_projects.append(
            {
                "project_id": project_id,
                "active_runs": active_runs,
                "max_no_progress_seconds": max_no_progress_seconds,
            }
        )
    no_progress_projects.sort(key=lambda item: float(item.get("max_no_progress_seconds", 0.0)), reverse=True)
    loop_state = _read_autonomous_loop_state()
    loop_stale = False
    loop_stale_seconds = 0.0
    loop_state_status = ""
    release_matrix = _read_release_matrix_snapshot()
    if isinstance(loop_state, dict):
        loop_state_status = str(loop_state.get("status") or "").strip().lower()
        hb = loop_state.get("updated_at", loop_state.get("finished_at", loop_state.get("started_at", 0.0)))
        try:
            hb_ts = float(hb or 0.0)
        except Exception:
            hb_ts = 0.0
        if hb_ts > 0:
            loop_stale_seconds = max(0.0, float(now_ts) - hb_ts)
            loop_stale = loop_stale_seconds >= float(loop_stale_threshold)
            # A stale terminal snapshot (ok/failed/stopped) is historical noise unless there are
            # active symptoms (stuck/no-progress runs) in current pipeline state.
            if loop_stale and loop_state_status in {"ok", "failed", "stopped", "idle"}:
                has_active_symptoms = bool(stuck_runs) or bool(no_progress_projects)
                if not has_active_symptoms:
                    loop_stale = False

    return web.json_response(
        {
            "status": "ok",
            "timestamp": now_ts,
            "summary": {
                "project_filter": project_filter or None,
                "include_runs": include_runs,
                "include_orphaned": include_orphaned,
                "projects_total": len(projects),
                "projects_with_pipeline_state": len(per_project),
                "tasks_total": len(tasks),
                "runs_total": len(runs),
                "docker_lane_enabled": bool(docker_lane.get("enabled")),
                "docker_lane_ready": bool(docker_lane.get("ready")),
                "orphaned_tasks_total": orphaned_tasks_total,
                "orphaned_runs_total": orphaned_runs_total,
                "tasks_by_status": _count_by(tasks, "status"),
                "runs_by_status": _count_by(runs, "status"),
                "runs_by_stage": _count_by(runs, "current_stage"),
                "guardrail_stops_total": guardrail_stops_total,
                "guardrail_stops_by_reason": guardrail_stops_by_reason,
                "terminal_failures_total": terminal_failures_total,
                "failure_taxonomy": failure_taxonomy,
                "release_matrix_status": release_matrix.get("status"),
                "release_matrix_must_passed": release_matrix.get("must_passed"),
                "release_matrix_must_total": release_matrix.get("must_total"),
                "release_matrix_must_failed": release_matrix.get("must_failed"),
                "release_matrix_must_missing": release_matrix.get("must_missing"),
                "release_matrix_generated_at": release_matrix.get("generated_at"),
            },
            "alerts": {
                "stuck_threshold_seconds": stuck_threshold,
                "stuck_runs_total": len(stuck_runs),
                "stuck_runs": stuck_runs[:50],
                "no_progress_threshold_seconds": no_progress_threshold,
                "no_progress_projects_total": len(no_progress_projects),
                "no_progress_projects": no_progress_projects[:50],
                "loop_stale_threshold_seconds": loop_stale_threshold,
                "loop_stale": loop_stale,
                "loop_stale_seconds": loop_stale_seconds,
            },
            "projects": per_project,
            "active_runs": active_runs_details[:50] if include_runs else [],
            "release_matrix": release_matrix,
            "runtime": {
                "docker_lane": docker_lane,
            },
            "loop": {
                "state_path": str(_autonomous_loop_state_path()),
                "state": loop_state or {},
                "stale": loop_stale,
                "stale_seconds": loop_stale_seconds,
                "stale_threshold_seconds": loop_stale_threshold,
            },
        }
    )


async def handle_autonomous_ops_remediate_stale(request: web.Request) -> web.Response:
    """POST /api/autonomous/ops/remediate-stale

    Bulk-remediate stale active runs (`queued|in_progress`) older than threshold.
    Default mode is dry-run to provide safe operator preview.
    """
    store = _get_store(request)

    try:
        req = await request.json()
    except Exception:
        req = {}
    if not isinstance(req, dict):
        return web.json_response({"error": "JSON object expected"}, status=400)

    dry_run = bool(req.get("dry_run", True))
    confirm = bool(req.get("confirm", False))
    project_filter = str(req.get("project_id") or request.query.get("project_id") or "").strip()
    include_orphaned = _parse_bool_param(
        req.get("include_orphaned", request.query.get("include_orphaned")),
        default=False,
    )
    reason = str(req.get("reason") or "ops_remediation_stale_run").strip() or "ops_remediation_stale_run"
    action = str(req.get("action") or "escalated").strip().lower()
    if action not in {"failed", "escalated"}:
        return web.json_response({"error": "action must be one of: failed, escalated"}, status=400)
    if not dry_run and not confirm:
        return web.json_response({"error": "confirm=true is required when dry_run=false"}, status=400)

    raw_older = req.get("older_than_seconds", _stuck_run_threshold_seconds())
    raw_max_runs = req.get("max_runs", 100)
    try:
        older_than_seconds = int(raw_older)
    except Exception:
        return web.json_response({"error": "older_than_seconds must be an integer"}, status=400)
    try:
        max_runs = int(raw_max_runs)
    except Exception:
        return web.json_response({"error": "max_runs must be an integer"}, status=400)
    if older_than_seconds < 60:
        return web.json_response({"error": "older_than_seconds must be >= 60"}, status=400)
    if max_runs < 1 or max_runs > 2000:
        return web.json_response({"error": "max_runs must be between 1 and 2000"}, status=400)

    now_ts = time.time()
    manager = request.app[APP_KEY_MANAGER]
    projects = manager.list_projects() if hasattr(manager, "list_projects") else []
    active_project_ids = {str(item.get("id", "")).strip() for item in projects if str(item.get("id", "")).strip()}
    candidates: list[dict[str, Any]] = []
    orphaned_skipped_total = 0
    for run in store.list_all_runs():
        if run.status not in {"queued", "in_progress"}:
            continue
        if project_filter and run.project_id != project_filter:
            continue
        if not include_orphaned and not project_filter and run.project_id not in active_project_ids:
            orphaned_skipped_total += 1
            continue
        stale_for = max(0.0, float(now_ts) - float(run.updated_at))
        if stale_for < float(older_than_seconds):
            continue
        candidates.append(
            {
                "project_id": run.project_id,
                "run_id": run.id,
                "task_id": run.task_id,
                "status": run.status,
                "current_stage": run.current_stage,
                "updated_at": run.updated_at,
                "stale_for_seconds": stale_for,
            }
        )
    candidates.sort(key=lambda row: float(row.get("stale_for_seconds", 0.0)), reverse=True)
    selected = candidates[:max_runs]

    remediated: list[dict[str, Any]] = []
    if not dry_run:
        for row in selected:
            run = store.get_run(str(row.get("run_id") or ""))
            if run is None:
                continue
            if run.status not in {"queued", "in_progress"}:
                continue

            stage_states = dict(run.stage_states)
            current_stage = str(run.current_stage or "").strip()
            if current_stage and current_stage in stage_states:
                stage_states[current_stage] = "failed"

            artifacts = dict(run.artifacts) if isinstance(run.artifacts, dict) else {}
            events = artifacts.get("events")
            if not isinstance(events, list):
                events = []
            events.append(
                {
                    "type": "ops_remediation",
                    "timestamp": now_ts,
                    "data": {
                        "reason": reason,
                        "action": action,
                        "older_than_seconds": older_than_seconds,
                    },
                }
            )
            artifacts["events"] = events

            updated = store.update_run(
                run.id,
                {
                    "status": action,
                    "stage_states": stage_states,
                    "artifacts": artifacts,
                    "finished_at": now_ts,
                },
            )
            if updated is None:
                continue

            task = store.get_task(run.task_id)
            if task is not None and task.status == "in_progress":
                store.update_task(task.id, {"status": "blocked"})

            remediated.append(
                {
                    "project_id": run.project_id,
                    "run_id": run.id,
                    "task_id": run.task_id,
                    "from_status": row.get("status"),
                    "to_status": action,
                    "stale_for_seconds": row.get("stale_for_seconds"),
                }
            )

    return web.json_response(
        {
            "status": "ok",
            "dry_run": dry_run,
            "project_filter": project_filter or None,
            "include_orphaned": include_orphaned,
            "action": action,
            "older_than_seconds": older_than_seconds,
            "max_runs": max_runs,
            "orphaned_skipped_total": orphaned_skipped_total,
            "candidates_total": len(candidates),
            "selected_total": len(selected),
            "selected": selected,
            "remediated_total": len(remediated),
            "remediated": remediated,
        }
    )


async def handle_autonomous_ops_purge_orphaned(request: web.Request) -> web.Response:
    """POST /api/autonomous/ops/purge-orphaned

    Remove tasks/runs whose ``project_id`` no longer exists in project registry.
    Default mode is dry-run.
    """
    store = _get_store(request)
    manager = request.app[APP_KEY_MANAGER]

    try:
        req = await request.json()
    except Exception:
        req = {}
    if not isinstance(req, dict):
        return web.json_response({"error": "JSON object expected"}, status=400)

    dry_run = _parse_bool_param(req.get("dry_run"), default=True)
    confirm = _parse_bool_param(req.get("confirm"), default=False)
    if not dry_run and not confirm:
        return web.json_response({"error": "confirm=true is required when dry_run=false"}, status=400)

    raw_max_projects = req.get("max_projects", 2000)
    try:
        max_projects = int(raw_max_projects)
    except Exception:
        return web.json_response({"error": "max_projects must be an integer"}, status=400)
    if max_projects < 1 or max_projects > 10000:
        return web.json_response({"error": "max_projects must be between 1 and 10000"}, status=400)

    projects = manager.list_projects() if hasattr(manager, "list_projects") else []
    active_project_ids = {str(item.get("id", "")).strip() for item in projects if str(item.get("id", "")).strip()}

    orphaned: dict[str, dict[str, int]] = {}
    for task in store.list_all_tasks():
        project_id = str(task.project_id or "").strip()
        if not project_id or project_id in active_project_ids:
            continue
        bucket = orphaned.setdefault(project_id, {"tasks": 0, "runs": 0})
        bucket["tasks"] = int(bucket["tasks"]) + 1
    for run in store.list_all_runs():
        project_id = str(run.project_id or "").strip()
        if not project_id or project_id in active_project_ids:
            continue
        bucket = orphaned.setdefault(project_id, {"tasks": 0, "runs": 0})
        bucket["runs"] = int(bucket["runs"]) + 1

    rows = [
        {
            "project_id": project_id,
            "tasks": int(stats.get("tasks", 0)),
            "runs": int(stats.get("runs", 0)),
            "total": int(stats.get("tasks", 0)) + int(stats.get("runs", 0)),
        }
        for project_id, stats in orphaned.items()
    ]
    rows.sort(key=lambda item: (int(item["total"]), int(item["runs"]), int(item["tasks"])), reverse=True)
    selected = rows[:max_projects]

    purged: list[dict[str, Any]] = []
    if not dry_run:
        for row in selected:
            project_id = str(row.get("project_id") or "").strip()
            if not project_id:
                continue
            removed = store.delete_project_state(project_id)
            purged.append(
                {
                    "project_id": project_id,
                    "tasks_removed": int(removed.get("tasks_removed", 0)),
                    "runs_removed": int(removed.get("runs_removed", 0)),
                }
            )

    return web.json_response(
        {
            "status": "ok",
            "dry_run": dry_run,
            "active_projects_total": len(active_project_ids),
            "orphaned_projects_total": len(rows),
            "selected_total": len(selected),
            "selected": selected,
            "purged_total": len(purged),
            "purged": purged,
        }
    )


def register_routes(app: web.Application) -> None:
    if APP_KEY_AUTONOMOUS_STORE not in app:
        app[APP_KEY_AUTONOMOUS_STORE] = AutonomousPipelineStore()

    app.router.add_get("/api/autonomous/backlog/intake/template", handle_backlog_intake_template)
    app.router.add_post("/api/autonomous/backlog/intake/validate", handle_backlog_intake_validate)
    app.router.add_get("/api/projects/{project_id}/autonomous/backlog", handle_backlog_list)
    app.router.add_post("/api/projects/{project_id}/autonomous/backlog", handle_backlog_create)
    app.router.add_patch("/api/projects/{project_id}/autonomous/backlog/{task_id}", handle_backlog_update)

    app.router.add_get("/api/projects/{project_id}/autonomous/runs", handle_pipeline_runs_list)
    app.router.add_post("/api/projects/{project_id}/autonomous/runs", handle_pipeline_run_create)
    app.router.add_post("/api/projects/{project_id}/autonomous/dispatch-next", handle_pipeline_dispatch_next)
    app.router.add_post("/api/projects/{project_id}/autonomous/execute-next", handle_pipeline_execute_next)
    app.router.add_post("/api/projects/{project_id}/autonomous/loop/tick", handle_pipeline_loop_tick)
    app.router.add_post("/api/autonomous/loop/tick-all", handle_pipeline_loop_tick_all)
    app.router.add_post("/api/autonomous/loop/run-cycle", handle_pipeline_loop_run_cycle)
    app.router.add_post("/api/autonomous/loop/run-cycle/report", handle_pipeline_loop_run_cycle_report)
    app.router.add_get("/api/projects/{project_id}/autonomous/runs/{run_id}", handle_pipeline_run_get)
    app.router.add_get("/api/projects/{project_id}/autonomous/runs/{run_id}/report", handle_pipeline_run_report)
    app.router.add_post("/api/projects/{project_id}/autonomous/runs/{run_id}/advance", handle_pipeline_run_advance)
    app.router.add_post("/api/projects/{project_id}/autonomous/runs/{run_id}/evaluate", handle_pipeline_run_evaluate)
    app.router.add_post("/api/projects/{project_id}/autonomous/runs/{run_id}/auto-next", handle_pipeline_run_auto_next)
    app.router.add_post(
        "/api/projects/{project_id}/autonomous/runs/{run_id}/run-until-terminal",
        handle_pipeline_run_until_terminal,
    )
    app.router.add_post(
        "/api/projects/{project_id}/autonomous/runs/{run_id}/evaluate/github",
        handle_pipeline_run_evaluate_github,
    )
    app.router.add_get("/api/autonomous/ops/status", handle_autonomous_ops_status)
    app.router.add_post("/api/autonomous/ops/remediate-stale", handle_autonomous_ops_remediate_stale)
    app.router.add_post("/api/autonomous/ops/purge-orphaned", handle_autonomous_ops_purge_orphaned)

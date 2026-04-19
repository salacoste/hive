#!/usr/bin/env python3
"""Container-first E2E smoke for autonomous delivery flows.

Scenarios:
1) real_repo: existing project/repository flow.
2) template_repo: temporary template-based project flow.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_TEMPLATE_REPOSITORY = "https://github.com/aden-hive/hive"


@dataclass
class ApiClient:
    base_url: str
    timeout: int

    def _url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url.rstrip('/')}/api{path}"

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._url(path),
            method=method.upper(),
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                status = int(resp.status)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            status = int(exc.code)
        except Exception as exc:
            return 599, {"error": f"request failed: {exc}"}

        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return status, {"raw": raw}
        if isinstance(data, dict):
            return status, data
        return status, {"data": data}


def _slug(text: str) -> str:
    lowered = "".join(ch if ch.isalnum() else "-" for ch in text.lower())
    compact = "-".join(part for part in lowered.split("-") if part)
    return compact[:40] or "project"


def _extract_pr_url(report_payload: dict[str, Any]) -> str:
    report = report_payload.get("report")
    if not isinstance(report, dict):
        return ""
    pr = report.get("pr")
    if not isinstance(pr, dict):
        return ""
    return str(pr.get("url") or "").strip()


def _looks_like_issue_reference(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    if re.search(r"https://github\.com/[^/\s]+/[^/\s]+/issues/\d+", value):
        return True
    return bool(re.search(r"\b[^/\s]+/[^#\s]+#\d+\b", value))


def _env_bool(key: str, *, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _tcp_endpoint_reachable(host: str, port: int, *, timeout: float = 0.2) -> bool:
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError:
        return False
    sock.close()
    return True


def _resolve_default_base_url() -> str:
    explicit = str(os.environ.get("HIVE_DELIVERY_E2E_BASE_URL", "")).strip()
    if explicit:
        return explicit
    shared = str(os.environ.get("HIVE_BASE_URL", "")).strip()
    if shared:
        return shared
    if _tcp_endpoint_reachable("localhost", 8787):
        return "http://localhost:8787"
    if _tcp_endpoint_reachable("hive-core", 8787):
        return "http://hive-core:8787"
    return "http://localhost:8787"


def _resolve_template_repository(repository: str) -> tuple[str, str]:
    explicit = str(repository or "").strip()
    if explicit:
        return explicit, "explicit"
    return DEFAULT_TEMPLATE_REPOSITORY, "default_fallback"


def _resolve_real_workspace_path(*, client: ApiClient, project_id: str, explicit_workspace_path: str) -> str:
    explicit = str(explicit_workspace_path or "").strip()
    if explicit:
        return explicit
    status, payload = client.request("GET", f"/projects/{urllib.parse.quote(project_id, safe='')}")
    if status >= 400 or not isinstance(payload, dict):
        return ""
    return str(payload.get("workspace_path") or "").strip()


def _ensure_execution_session(
    *,
    client: ApiClient,
    project_id: str,
    agent_path: str,
    session_id: str,
    model_profile: str,
    model: str,
) -> tuple[str, dict[str, Any] | None]:
    agent = str(agent_path or "").strip()
    if not agent:
        return "", None
    payload: dict[str, Any] = {"project_id": project_id, "agent_path": agent}
    profile = str(model_profile or "").strip()
    if profile:
        payload["model_profile"] = profile
    resolved_model = str(model or "").strip()
    if resolved_model:
        payload["model"] = resolved_model
    sid = str(session_id or "").strip()
    if sid:
        payload["session_id"] = sid
    status, body = client.request("POST", "/sessions", payload)
    if status >= 400:
        return "", {
            "error": f"session create/load failed: {body.get('error') or status}",
            "details": body,
            "status": status,
        }
    resolved = str(body.get("session_id") or body.get("id") or "").strip()
    if not resolved:
        return "", {"error": "session create/load returned empty session_id", "details": body, "status": status}
    return resolved, None


def _is_repo_developer_agent(agent_path: str) -> bool:
    normalized = str(agent_path or "").strip().replace("\\", "/")
    if not normalized:
        return False
    return normalized.endswith("/repo_developer") or normalized.endswith("repo_developer")


def _ensure_real_project(
    *,
    client: ApiClient,
    project_id: str,
    repository: str,
) -> tuple[str, bool, dict[str, Any] | None]:
    target = str(project_id or "").strip() or "default"
    get_status, get_payload = client.request("GET", f"/projects/{urllib.parse.quote(target, safe='')}")
    if get_status < 400:
        return target, False, None
    if get_status != 404:
        return target, False, {"error": f"project lookup failed: {get_payload.get('error') or get_status}", "details": get_payload}

    fallback_id = f"e2e-real-{int(time.time())}"
    create_status, create_payload = client.request(
        "POST",
        "/projects",
        {
            "name": "E2E Real Repo",
            "description": "Temporary real-repo project for autonomous delivery smoke",
            "project_id": fallback_id,
            "repository": repository,
        },
    )
    if create_status >= 400:
        return fallback_id, False, {"error": f"project create failed: {create_payload.get('error') or create_status}", "details": create_payload}
    return fallback_id, True, None


def _run_flow(
    *,
    client: ApiClient,
    project_id: str,
    repository: str,
    task_title: str,
    task_goal: str,
    acceptance_criteria: list[str],
    max_steps: int,
    onboarding_payload: dict[str, Any],
    allow_onboarding_not_ready: bool,
    bind_repository: bool = True,
    session_id: str = "",
    require_terminal_success: bool = False,
    terminal_max_steps: int = 20,
    terminal_wait_seconds: int = 60,
    terminal_poll_seconds: float = 1.0,
    github_no_checks_policy: str = "",
) -> tuple[bool, dict[str, Any]]:
    result: dict[str, Any] = {
        "project_id": project_id,
        "repository": repository,
        "steps": [],
        "trace": {},
    }

    if repository.strip() and bind_repository:
        bind_status, bind_payload = client.request(
            "POST",
            f"/projects/{urllib.parse.quote(project_id, safe='')}/repository/bind",
            {"repository": repository},
        )
        result["steps"].append({"name": "repository_bind", "status": bind_status})
        if bind_status >= 400:
            if bind_status in {404, 405}:
                result["trace"]["repository_bind_compatibility_fallback"] = True
                result["trace"]["repository_bind_status"] = bind_status
            else:
                result["error"] = f"repository_bind failed: {bind_payload.get('error') or bind_status}"
                result["details"] = bind_payload
                return False, result
        else:
            repo = bind_payload.get("repository")
            if isinstance(repo, dict):
                result["trace"]["repository_url"] = str(repo.get("html_url") or "").strip()
                result["trace"]["repository_full_name"] = str(repo.get("full_name") or "").strip()

    requested_workspace = str(onboarding_payload.get("workspace_path") or "").strip()
    result["trace"]["onboarding_workspace_requested"] = requested_workspace or None

    onboard_status, onboard_payload = client.request(
        "POST",
        f"/projects/{urllib.parse.quote(project_id, safe='')}/onboarding",
        onboarding_payload,
    )
    result["steps"].append({"name": "onboarding", "status": onboard_status})
    if onboard_status >= 400:
        result["error"] = f"onboarding failed: {onboard_payload.get('error') or onboard_status}"
        result["details"] = onboard_payload
        return False, result

    result["trace"]["onboarding_ready"] = bool(onboard_payload.get("ready"))
    result["trace"]["workspace_path"] = str(onboard_payload.get("workspace_path") or "").strip()
    onboarding_deferred = False
    if not bool(onboard_payload.get("ready")):
        checks = onboard_payload.get("checks")
        failed_checks: list[str] = []
        if isinstance(checks, list):
            for item in checks:
                if not isinstance(item, dict):
                    continue
                if str(item.get("status") or "").strip().lower() == "fail":
                    failed_checks.append(str(item.get("id") or "").strip())
        result["trace"]["onboarding_failed_checks"] = [x for x in failed_checks if x]
        if allow_onboarding_not_ready:
            onboarding_deferred = True
            result["trace"]["onboarding_deferred"] = True
            result["trace"]["deferred_reason"] = "onboarding_not_ready"
        else:
            result["error"] = "onboarding is not ready"
            result["trace"]["onboarding_failed_checks"] = [x for x in failed_checks if x]
            return False, result

    no_checks_policy = str(github_no_checks_policy or "").strip().lower()
    if no_checks_policy:
        patch_status, patch_payload = client.request(
            "PATCH",
            f"/projects/{urllib.parse.quote(project_id, safe='')}/execution-template",
            {"execution_template": {"no_checks_policy": no_checks_policy}},
        )
        result["steps"].append({"name": "execution_template_patch", "status": patch_status})
        if patch_status >= 400:
            result["error"] = (
                f"execution_template_patch failed: {patch_payload.get('error') or patch_status}"
            )
            result["details"] = patch_payload
            return False, result
        result["trace"]["github_no_checks_policy"] = no_checks_policy

    task_status, task_payload = client.request(
        "POST",
        f"/projects/{urllib.parse.quote(project_id, safe='')}/autonomous/backlog",
        {
            "title": task_title,
            "goal": task_goal,
            "acceptance_criteria": acceptance_criteria,
            "priority": "high",
            "repository": repository,
        },
    )
    result["steps"].append({"name": "backlog_create", "status": task_status})
    if task_status >= 400:
        result["error"] = f"backlog_create failed: {task_payload.get('error') or task_status}"
        result["details"] = task_payload
        return False, result
    task_id = str(task_payload.get("id") or "").strip()
    result["trace"]["task_id"] = task_id

    execute_status, execute_payload = client.request(
        "POST",
        f"/projects/{urllib.parse.quote(project_id, safe='')}/autonomous/execute-next",
        (
            {
            "max_steps": max_steps,
            "auto_start": True,
            "repository": repository,
            "summary": "autonomous_delivery_e2e_smoke",
            }
            | ({"session_id": session_id} if str(session_id or "").strip() else {})
        ),
    )
    result["steps"].append({"name": "execute_next", "status": execute_status})
    if execute_status >= 400:
        result["error"] = f"execute_next failed: {execute_payload.get('error') or execute_status}"
        result["details"] = execute_payload
        return False, result

    run_id = str(execute_payload.get("run_id") or "").strip()
    result["trace"]["run_id"] = run_id
    result["trace"]["terminal"] = bool(execute_payload.get("terminal"))
    result["trace"]["terminal_status"] = str(execute_payload.get("terminal_status") or "").strip() or None
    selected_task = execute_payload.get("selected_task")
    if isinstance(selected_task, dict):
        result["trace"]["selected_task_id"] = str(selected_task.get("id") or "").strip() or None

    if run_id:
        run_status, run_payload = client.request(
            "GET",
            f"/projects/{urllib.parse.quote(project_id, safe='')}/autonomous/runs/{urllib.parse.quote(run_id, safe='')}",
        )
        result["steps"].append({"name": "run_get", "status": run_status})
        if run_status < 400 and isinstance(run_payload, dict):
            run_task_id = str(run_payload.get("task_id") or "").strip()
            if run_task_id:
                result["trace"]["run_task_id"] = run_task_id
            if task_id and run_task_id and run_task_id != task_id:
                result["error"] = "execute_next selected different active run (task mismatch)"
                result["details"] = {
                    "expected_task_id": task_id,
                    "selected_run_id": run_id,
                    "selected_run_task_id": run_task_id,
                }
                return False, result
        report_path = f"/projects/{urllib.parse.quote(project_id, safe='')}/autonomous/runs/{urllib.parse.quote(run_id, safe='')}/report"
        report_status, report_payload = client.request("GET", report_path)
        result["steps"].append({"name": "run_report", "status": report_status})
        result["trace"]["report_endpoint"] = f"/api/projects/{project_id}/autonomous/runs/{run_id}/report"
        if report_status < 400:
            pr_url = _extract_pr_url(report_payload)
            if pr_url:
                result["trace"]["pr_url"] = pr_url
        if require_terminal_success:
            deadline = time.time() + max(1, int(terminal_wait_seconds))
            terminal_payload: dict[str, Any] = {}
            terminal_status = 0
            attempts = 0
            while True:
                attempts += 1
                terminal_status, terminal_payload = client.request(
                    "POST",
                    f"/projects/{urllib.parse.quote(project_id, safe='')}/autonomous/runs/{urllib.parse.quote(run_id, safe='')}/run-until-terminal",
                    {
                        "max_steps": max(1, int(terminal_max_steps)),
                        "auto_start": True,
                        **({"session_id": session_id} if str(session_id or "").strip() else {}),
                    },
                )
                result["steps"].append(
                    {
                        "name": "run_until_terminal",
                        "status": terminal_status,
                        "attempt": attempts,
                    }
                )
                if terminal_status >= 400:
                    result["error"] = f"run_until_terminal failed: {terminal_payload.get('error') or terminal_status}"
                    result["details"] = terminal_payload
                    return False, result
                terminal = bool(terminal_payload.get("terminal"))
                resolved_terminal_status = str(terminal_payload.get("terminal_status") or "").strip()
                result["trace"]["terminal"] = terminal
                result["trace"]["terminal_status"] = resolved_terminal_status or None
                result["trace"]["terminal_poll_attempts"] = attempts
                if terminal:
                    if resolved_terminal_status != "completed":
                        result["error"] = f"run terminal status is {resolved_terminal_status or 'unknown'}"
                        result["details"] = terminal_payload
                        return False, result
                    break
                if time.time() >= deadline:
                    result["error"] = "run did not reach terminal state within timeout"
                    result["details"] = terminal_payload
                    return False, result
                time.sleep(max(0.1, float(terminal_poll_seconds)))
    if onboarding_deferred:
        result["trace"]["terminal_state"] = "manual_deferred_onboarding"

    return True, result


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous delivery E2E smoke")
    parser.add_argument(
        "--base-url",
        default=_resolve_default_base_url(),
        help="Hive core base URL",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("HIVE_DELIVERY_E2E_TIMEOUT", "120") or "120"),
        help="HTTP timeout seconds",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=int(os.environ.get("HIVE_DELIVERY_E2E_MAX_STEPS", "4") or "4"),
        help="max_steps for execute-next",
    )
    parser.add_argument(
        "--terminal-max-steps",
        type=int,
        default=int(os.environ.get("HIVE_DELIVERY_E2E_TERMINAL_MAX_STEPS", "20") or "20"),
        help="max_steps for run-until-terminal when --require-terminal-success is enabled",
    )
    parser.add_argument(
        "--terminal-wait-seconds",
        type=int,
        default=int(os.environ.get("HIVE_DELIVERY_E2E_TERMINAL_WAIT_SECONDS", "300") or "300"),
        help="wall-clock timeout to wait for terminal run status when --require-terminal-success is enabled",
    )
    parser.add_argument(
        "--terminal-poll-seconds",
        type=float,
        default=float(os.environ.get("HIVE_DELIVERY_E2E_TERMINAL_POLL_SECONDS", "1.0") or "1.0"),
        help="poll interval between run-until-terminal retries",
    )
    parser.add_argument("--skip-real", action="store_true", help="Skip real repository scenario")
    parser.add_argument("--skip-template", action="store_true", help="Skip template scenario")
    parser.add_argument(
        "--real-project-id",
        default=os.environ.get("HIVE_DELIVERY_E2E_REAL_PROJECT_ID", "default"),
        help="Project id for real repo scenario",
    )
    parser.add_argument(
        "--real-repository",
        default=os.environ.get("HIVE_DELIVERY_E2E_REAL_REPOSITORY", ""),
        help="Existing repository URL/slug for real scenario",
    )
    parser.add_argument(
        "--real-task-goal",
        default="Acceptance smoke: verify autonomous delivery flow on existing repository",
        help="Goal text for real repo scenario",
    )
    parser.add_argument(
        "--real-issue-url",
        default=os.environ.get("HIVE_DELIVERY_E2E_REAL_ISSUE_URL", "").strip(),
        help="Optional GitHub issue URL/reference. Required by issue-driven agents like repo_developer.",
    )
    parser.add_argument(
        "--real-agent-path",
        default=os.environ.get("HIVE_DELIVERY_E2E_REAL_AGENT_PATH", "").strip(),
        help="Optional agent path to create/load execution session for real scenario",
    )
    parser.add_argument(
        "--real-model-profile",
        default=os.environ.get("HIVE_DELIVERY_E2E_REAL_MODEL_PROFILE", "implementation").strip(),
        help="Model profile for real scenario execution session (e.g. implementation, heavy).",
    )
    parser.add_argument(
        "--real-model",
        default=os.environ.get("HIVE_DELIVERY_E2E_REAL_MODEL", "openai/gemini-3.1-pro-high").strip(),
        help="Primary model for real scenario execution session.",
    )
    parser.add_argument(
        "--real-session-id",
        default=os.environ.get("HIVE_DELIVERY_E2E_REAL_SESSION_ID", "").strip(),
        help="Optional fixed session_id when creating/loading execution session",
    )
    parser.add_argument(
        "--real-stack",
        default=os.environ.get("HIVE_DELIVERY_E2E_REAL_STACK", "").strip(),
        help="Optional stack override for real scenario onboarding (e.g. node|python|go|jvm|rust|fullstack)",
    )
    parser.add_argument(
        "--real-workspace-path",
        default=os.environ.get("HIVE_DELIVERY_E2E_REAL_WORKSPACE_PATH", ""),
        help="Workspace path for real scenario onboarding (fallback: project.workspace_path)",
    )
    parser.add_argument("--cleanup-real-created", action="store_true", default=True, help="Delete temporary real scenario project")
    parser.add_argument("--no-cleanup-real-created", dest="cleanup_real_created", action="store_false")
    parser.add_argument(
        "--template-id",
        default=os.environ.get("HIVE_DELIVERY_E2E_TEMPLATE_ID", "backend-python-api"),
        help="Template id for template scenario",
    )
    parser.add_argument(
        "--template-stack",
        default=os.environ.get("HIVE_DELIVERY_E2E_TEMPLATE_STACK", "python"),
        help="Stack for template scenario onboarding",
    )
    parser.add_argument(
        "--template-repository",
        default=os.environ.get("HIVE_DELIVERY_E2E_TEMPLATE_REPOSITORY", ""),
        help=f"Repository URL/slug for template scenario (fallback: {DEFAULT_TEMPLATE_REPOSITORY})",
    )
    parser.add_argument("--cleanup-template", action="store_true", default=True, help="Delete temp template project")
    parser.add_argument("--no-cleanup-template", dest="cleanup_template", action="store_false")
    parser.add_argument(
        "--strict-onboarding",
        action="store_true",
        help="Fail scenario when onboarding is not ready (default allows manual_deferred).",
    )
    parser.add_argument(
        "--out-json",
        default=os.environ.get("HIVE_DELIVERY_E2E_OUT_JSON", "").strip(),
        help="Optional output JSON path for summary artifact",
    )
    parser.add_argument(
        "--require-terminal-success",
        action="store_true",
        help="Require run-until-terminal to reach terminal_status=completed for each executed scenario.",
    )
    parser.add_argument(
        "--github-no-checks-policy",
        default=os.environ.get("HIVE_DELIVERY_E2E_GITHUB_NO_CHECKS_POLICY", "success").strip(),
        help="Optional execution_template no_checks_policy override (error|success|manual_pending).",
    )
    args = parser.parse_args()

    if _env_bool("HIVE_DELIVERY_E2E_SKIP_REAL", default=False):
        args.skip_real = True
    if _env_bool("HIVE_DELIVERY_E2E_SKIP_TEMPLATE", default=False):
        args.skip_template = True
    if _env_bool("HIVE_DELIVERY_E2E_STRICT_ONBOARDING", default=False):
        args.strict_onboarding = True
    if _env_bool("HIVE_DELIVERY_E2E_REQUIRE_TERMINAL_SUCCESS", default=False):
        args.require_terminal_success = True

    if args.max_steps < 1 or args.max_steps > 100:
        print("[fail] --max-steps must be between 1 and 100")
        return 2
    if args.terminal_max_steps < 1 or args.terminal_max_steps > 500:
        print("[fail] --terminal-max-steps must be between 1 and 500")
        return 2
    if args.terminal_wait_seconds < 1 or args.terminal_wait_seconds > 3600:
        print("[fail] --terminal-wait-seconds must be between 1 and 3600")
        return 2
    if args.terminal_poll_seconds <= 0 or args.terminal_poll_seconds > 60:
        print("[fail] --terminal-poll-seconds must be between 0 and 60")
        return 2

    client = ApiClient(base_url=args.base_url, timeout=args.timeout)
    started_at = time.time()
    results: list[dict[str, Any]] = []
    success = True
    allow_onboarding_not_ready = not bool(args.strict_onboarding)

    if not args.skip_real:
        real_repository = str(args.real_repository or "").strip()
        if not real_repository:
            results.append(
                {
                    "scenario": "real_repo",
                    "ok": True,
                    "skipped": True,
                    "reason": "real_repository_not_configured",
                }
            )
        else:
            resolved_real_project_id, real_project_created, real_project_error = _ensure_real_project(
                client=client,
                project_id=args.real_project_id,
                repository=real_repository,
            )
            if real_project_error:
                results.append(
                    {
                        "scenario": "real_repo",
                        "ok": False,
                        "error": str(real_project_error.get("error") or "project setup failed"),
                        "details": real_project_error.get("details") or {},
                    }
                )
                success = False
            else:
                if not resolved_real_project_id:
                    resolved_real_project_id = args.real_project_id
                execution_session_id, session_error = _ensure_execution_session(
                    client=client,
                    project_id=resolved_real_project_id,
                    agent_path=args.real_agent_path,
                    session_id=args.real_session_id,
                    model_profile=args.real_model_profile,
                    model=args.real_model,
                )
                if session_error:
                    results.append(
                        {
                            "scenario": "real_repo",
                            "ok": False,
                            "error": str(session_error.get("error") or "session setup failed"),
                            "details": session_error.get("details") or {},
                        }
                    )
                    success = False
                else:
                    real_task_goal = str(args.real_task_goal or "").strip()
                    goal_valid = True
                    if _is_repo_developer_agent(args.real_agent_path):
                        issue_ref = str(args.real_issue_url or "").strip()
                        if issue_ref and issue_ref not in real_task_goal:
                            if real_task_goal:
                                real_task_goal = f"{real_task_goal}\nIssue: {issue_ref}"
                            else:
                                real_task_goal = issue_ref
                        if not _looks_like_issue_reference(real_task_goal):
                            results.append(
                                {
                                    "scenario": "real_repo",
                                    "ok": False,
                                    "error": (
                                        "repo_developer requires issue reference in task goal "
                                        "(provide --real-issue-url or include owner/repo#N in --real-task-goal)"
                                    ),
                                    "project_used": resolved_real_project_id,
                                }
                            )
                            success = False
                            goal_valid = False
                    if goal_valid:
                        real_workspace_path = _resolve_real_workspace_path(
                            client=client,
                            project_id=resolved_real_project_id,
                            explicit_workspace_path=args.real_workspace_path,
                        )
                        real_onboarding_payload: dict[str, Any] = {"repository": real_repository}
                        if real_workspace_path:
                            real_onboarding_payload["workspace_path"] = real_workspace_path
                        real_stack = str(args.real_stack or "").strip()
                        if real_stack:
                            real_onboarding_payload["stack"] = real_stack
                        ok, payload = _run_flow(
                            client=client,
                            project_id=resolved_real_project_id,
                            repository=real_repository,
                            task_title="E2E smoke (real repo)",
                            task_goal=real_task_goal,
                            acceptance_criteria=[
                                "onboarding ready or manual_deferred",
                                "backlog task created",
                                "execute-next returns run metadata",
                            ],
                            max_steps=args.max_steps,
                            onboarding_payload=real_onboarding_payload,
                            allow_onboarding_not_ready=allow_onboarding_not_ready,
                            session_id=execution_session_id,
                            require_terminal_success=bool(args.require_terminal_success),
                            terminal_max_steps=args.terminal_max_steps,
                            terminal_wait_seconds=args.terminal_wait_seconds,
                            terminal_poll_seconds=args.terminal_poll_seconds,
                            github_no_checks_policy=args.github_no_checks_policy,
                        )
                        payload["scenario"] = "real_repo"
                        payload["ok"] = ok
                        payload["project_created"] = bool(real_project_created)
                        payload["project_used"] = resolved_real_project_id
                        if execution_session_id:
                            payload.setdefault("trace", {})["session_id"] = execution_session_id
                        results.append(payload)
                        success = success and ok
                        if real_project_created and args.cleanup_real_created:
                            delete_status, delete_payload = client.request(
                                "DELETE",
                                f"/projects/{urllib.parse.quote(resolved_real_project_id, safe='')}?force=1",
                            )
                            payload["cleanup"] = {
                                "status": delete_status,
                                "ok": delete_status < 400,
                                "error": (delete_payload.get("error") if isinstance(delete_payload, dict) else None),
                            }

    if not args.skip_template:
        template_repository, template_repository_source = _resolve_template_repository(args.template_repository)
        template_project_name = f"e2e-template-{int(time.time())}"
        template_project_id = f"{_slug(template_project_name)}-{str(int(time.time()))[-5:]}"
        create_status, create_payload = client.request(
            "POST",
            "/projects",
            {
                "name": template_project_name,
                "description": "Temporary project for autonomous delivery e2e smoke",
                "project_id": template_project_id,
                "repository": template_repository,
            },
        )
        if create_status >= 400:
            results.append(
                {
                    "scenario": "template_repo",
                    "ok": False,
                    "error": f"project create failed: {create_payload.get('error') or create_status}",
                    "details": create_payload,
                }
            )
            success = False
        else:
            created_id = str(create_payload.get("id") or template_project_id).strip() or template_project_id
            ok, payload = _run_flow(
                client=client,
                project_id=created_id,
                repository=template_repository,
                task_title="E2E smoke (template project)",
                task_goal="Acceptance smoke: verify autonomous delivery flow on template-based project",
                acceptance_criteria=[
                    "template onboarding ready or manual_deferred",
                    "backlog task created",
                    "execute-next returns run metadata",
                ],
                max_steps=args.max_steps,
                onboarding_payload={
                    "template_id": args.template_id,
                    "stack": args.template_stack,
                    "repository": template_repository,
                },
                allow_onboarding_not_ready=allow_onboarding_not_ready,
                bind_repository=False,
                require_terminal_success=bool(args.require_terminal_success),
                terminal_max_steps=args.terminal_max_steps,
                terminal_wait_seconds=args.terminal_wait_seconds,
                terminal_poll_seconds=args.terminal_poll_seconds,
                github_no_checks_policy=args.github_no_checks_policy,
            )
            payload["scenario"] = "template_repo"
            payload["ok"] = ok
            payload["project_created"] = created_id
            payload.setdefault("trace", {})["template_repository_source"] = template_repository_source
            results.append(payload)
            success = success and ok

            if args.cleanup_template:
                delete_status, delete_payload = client.request(
                    "DELETE",
                    f"/projects/{urllib.parse.quote(created_id, safe='')}?force=1",
                )
                payload["cleanup"] = {
                    "status": delete_status,
                    "ok": delete_status < 400,
                    "error": (delete_payload.get("error") if isinstance(delete_payload, dict) else None),
                }

    if not results:
        print("[fail] no scenario executed (all were skipped)")
        return 2

    skipped_total = sum(1 for row in results if bool(row.get("skipped")))
    hard_fail_total = sum(1 for row in results if not bool(row.get("ok")))
    summary_status = "ok" if hard_fail_total == 0 else "failed"
    summary = {
        "status": summary_status,
        "started_at": started_at,
        "finished_at": time.time(),
        "duration_seconds": round(time.time() - started_at, 3),
        "base_url": args.base_url.rstrip("/"),
        "strict_onboarding": bool(args.strict_onboarding),
        "scenarios_total": len(results),
        "scenarios_ok": sum(1 for row in results if bool(row.get("ok"))),
        "scenarios_failed": hard_fail_total,
        "scenarios_skipped": skipped_total,
        "results": results,
    }
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.out_json:
        out_path = Path(args.out_json).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
        summary["out_json"] = str(out_path)
        rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    print(rendered)
    return 0 if hard_fail_total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Project lifecycle routes for grouping sessions by repository/application."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

from aiohttp import web

from framework.server.app import APP_KEY_CREDENTIAL_STORE, APP_KEY_MANAGER
from framework.server.autonomous_pipeline import AutonomousPipelineStore
from framework.server.project_execution import (
    normalize_execution_template,
    resolve_execution_template,
)
from framework.server.project_metrics import compute_project_metrics
from framework.server.project_onboarding import run_project_onboarding
from framework.server.project_policy import normalize_policy_overrides, resolve_effective_policy
from framework.server.project_retention import (
    apply_retention_plan,
    build_retention_plan,
    normalize_retention_policy,
    resolve_retention_policy,
)
from framework.server.project_toolchain import (
    build_apply_commands,
    build_env_exports,
    detect_toolchain_plan,
    resolve_toolchain_source,
)
from framework.server.project_templates import get_project_template, list_project_templates
from framework.server.session_manager import SessionManager

logger = logging.getLogger(__name__)

_GITHUB_REPO_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _get_manager(request: web.Request) -> SessionManager:
    return request.app[APP_KEY_MANAGER]


class _GitHubProvisionError(RuntimeError):
    """Raised when GitHub repository provisioning fails with mapped HTTP status."""

    def __init__(self, message: str, *, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


def _resolve_github_token(request: web.Request) -> str:
    """Resolve GitHub token from credential store first, then environment."""
    store = request.app.get(APP_KEY_CREDENTIAL_STORE)
    if store is not None:
        try:
            token = store.get_key("github", "access_token") or store.get_key("github", "api_key")
            if isinstance(token, str) and token.strip():
                return token.strip()
            fallback = store.get("github")
            if isinstance(fallback, str) and fallback.strip():
                return fallback.strip()
        except Exception:
            logger.debug("GitHub token lookup in credential store failed", exc_info=True)

    for env_key in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"):
        token = os.environ.get(env_key, "").strip()
        if token:
            return token
    return ""


def _parse_github_error_detail(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return "Unknown GitHub API error"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text[:300]
    if not isinstance(data, dict):
        return text[:300]
    message = str(data.get("message") or "").strip()
    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            field = str(first.get("field") or "").strip()
            code = str(first.get("code") or "").strip()
            err_message = str(first.get("message") or "").strip()
            parts = [p for p in (field, code, err_message) if p]
            if parts:
                return f"{message}: {'/'.join(parts)}" if message else "/".join(parts)
    return message or text[:300]


def _github_api_json(
    *,
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: bytes | None = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        method=method.upper(),
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "hive-project-provisioner",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        safe_detail = _parse_github_error_detail(detail)
        if e.code in {401, 403, 404}:
            raise _GitHubProvisionError(f"GitHub API error ({e.code}): {safe_detail}", status=e.code) from e
        if e.code == 422:
            raise _GitHubProvisionError(f"GitHub repository validation failed: {safe_detail}", status=409) from e
        raise _GitHubProvisionError(f"GitHub API error ({e.code}): {safe_detail}", status=502) from e
    except urllib.error.URLError as e:
        raise _GitHubProvisionError(f"GitHub API unreachable: {e}", status=502) from e
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as e:
        raise _GitHubProvisionError("GitHub API returned invalid JSON", status=502) from e
    if not isinstance(parsed, dict):
        raise _GitHubProvisionError("GitHub API returned unexpected payload", status=502)
    return parsed


def _github_create_repository(
    *,
    token: str,
    name: str,
    owner: str | None,
    visibility: str,
    description: str,
    initialize_readme: bool,
) -> dict[str, Any]:
    owner_value = (owner or "").strip()
    if owner_value:
        endpoint = f"https://api.github.com/orgs/{owner_value}/repos"
    else:
        endpoint = "https://api.github.com/user/repos"
    payload: dict[str, Any] = {
        "name": name,
        "description": description,
        "auto_init": initialize_readme,
    }
    if visibility == "internal":
        payload["visibility"] = "internal"
    else:
        payload["private"] = visibility != "public"
    return _github_api_json(method="POST", url=endpoint, token=token, payload=payload)


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
    return ""


def _github_get_repository(*, token: str, repository: str) -> dict[str, Any]:
    slug = _normalize_github_repository(repository)
    if not slug:
        raise ValueError("repository must be in owner/name format or GitHub URL")
    return _github_api_json(
        method="GET",
        url=f"https://api.github.com/repos/{slug}",
        token=token,
        payload=None,
    )


def _parse_max_runs(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError("max_concurrent_runs must be a positive integer")
    if parsed <= 0:
        raise ValueError("max_concurrent_runs must be a positive integer")
    return parsed


def _normalize_environment_profile(raw: object) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("environment_profile must be an object")

    normalized: dict[str, Any] = {}

    required_credentials_raw = raw.get("required_credentials")
    if required_credentials_raw is not None:
        if not isinstance(required_credentials_raw, list):
            raise ValueError("environment_profile.required_credentials must be an array")
        normalized["required_credentials"] = [
            str(x).strip() for x in required_credentials_raw if str(x).strip()
        ]

    def _normalize_endpoint_rows(field_name: str) -> list[dict[str, Any]]:
        value = raw.get(field_name)
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f"environment_profile.{field_name} must be an array")
        rows: list[dict[str, Any]] = []
        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                raise ValueError(f"environment_profile.{field_name}[{idx}] must be an object")
            name = str(item.get("name") or "").strip()
            endpoint = str(item.get("endpoint") or "").strip()
            required = bool(item.get("required", True))
            if not name:
                raise ValueError(f"environment_profile.{field_name}[{idx}].name is required")
            rows.append(
                {
                    "name": name,
                    "endpoint": endpoint,
                    "required": required,
                    "engine": str(item.get("engine") or "").strip() if field_name == "databases" else "",
                }
            )
        return rows

    services = _normalize_endpoint_rows("services")
    databases = _normalize_endpoint_rows("databases")
    if services:
        normalized["services"] = services
    if databases:
        normalized["databases"] = databases
    return normalized


def _environment_preflight(
    *,
    profile: dict[str, Any],
    credential_store: Any,
) -> dict[str, Any]:
    required_credentials = profile.get("required_credentials")
    required_credentials = required_credentials if isinstance(required_credentials, list) else []
    services = profile.get("services")
    services = services if isinstance(services, list) else []
    databases = profile.get("databases")
    databases = databases if isinstance(databases, list) else []

    credentials_rows: list[dict[str, Any]] = []
    missing_credentials: list[str] = []
    for item in required_credentials:
        cid = str(item or "").strip()
        if not cid:
            continue
        available = False
        try:
            available = bool(credential_store.get_credential(cid, refresh_if_needed=False)) or bool(
                credential_store.get(cid)
            )
        except Exception:
            available = False
        credentials_rows.append({"credential_id": cid, "available": available})
        if not available:
            missing_credentials.append(cid)

    def _check_rows(rows: list[dict[str, Any]], kind: str) -> tuple[list[dict[str, Any]], list[str]]:
        checked: list[dict[str, Any]] = []
        missing: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            endpoint = str(row.get("endpoint") or "").strip()
            required = bool(row.get("required", True))
            ok = bool(endpoint) or (not required)
            checked.append(
                {
                    "name": name,
                    "endpoint": endpoint,
                    "required": required,
                    "ok": ok,
                    "kind": kind,
                    "engine": str(row.get("engine") or "").strip(),
                }
            )
            if required and not endpoint:
                missing.append(name or kind)
        return checked, missing

    service_rows, missing_services = _check_rows(services, "service")
    database_rows, missing_databases = _check_rows(databases, "database")
    ready = not missing_credentials and not missing_services and not missing_databases
    return {
        "ready": ready,
        "credentials": credentials_rows,
        "services": service_rows,
        "databases": database_rows,
        "missing": {
            "credentials": missing_credentials,
            "services": missing_services,
            "databases": missing_databases,
        },
        "summary": {
            "required_credentials": len(credentials_rows),
            "required_services": len([r for r in service_rows if r.get("required")]),
            "required_databases": len([r for r in database_rows if r.get("required")]),
        },
    }


async def handle_list_projects(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    return web.json_response(
        {
            "default_project_id": manager.default_project_id(),
            "projects": manager.list_projects(),
        }
    )


async def handle_projects_metrics(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    projects = manager.list_projects()
    data = []
    for project in projects:
        project_id = str(project.get("id") or "")
        if not project_id:
            continue
        active_sessions = len(manager.list_sessions(project_id=project_id))
        metrics = compute_project_metrics(project_id=project_id, active_sessions=active_sessions)
        data.append(
            {
                "project": {
                    "id": project_id,
                    "name": project.get("name") or project_id,
                    "repository": project.get("repository") or "",
                },
                "summary": metrics.get("summary", {}),
                "kpis": metrics.get("kpis", {}),
            }
        )
    data.sort(
        key=lambda item: (
            item.get("kpis", {}).get("success_rate") is not None,
            item.get("kpis", {}).get("success_rate") or -1,
            item.get("summary", {}).get("executions_total") or 0,
        ),
        reverse=True,
    )
    return web.json_response({"projects": data})


async def handle_project_templates(request: web.Request) -> web.Response:
    return web.json_response({"templates": list_project_templates()})


async def handle_create_project(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    body = await request.json() if request.can_read_body else {}
    name = str(body.get("name") or "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    try:
        max_runs = _parse_max_runs(body.get("max_concurrent_runs"))
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    try:
        overrides = normalize_policy_overrides(body.get("policy_overrides") or {})
    except (TypeError, ValueError) as e:
        return web.json_response({"error": str(e)}, status=400)
    try:
        policy_binding = normalize_policy_overrides(body.get("policy_binding") or {})
    except (TypeError, ValueError) as e:
        return web.json_response({"error": str(e)}, status=400)
    try:
        retention_policy = normalize_retention_policy(body.get("retention_policy") or {})
    except (TypeError, ValueError) as e:
        return web.json_response({"error": str(e)}, status=400)
    try:
        execution_template = normalize_execution_template(body.get("execution_template") or {})
    except (TypeError, ValueError) as e:
        return web.json_response({"error": str(e)}, status=400)
    try:
        environment_profile = _normalize_environment_profile(body.get("environment_profile") or {})
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    resolved_overrides = overrides or policy_binding
    project = manager.create_project(
        name=name,
        description=str(body.get("description") or "").strip(),
        repository=str(body.get("repository") or "").strip(),
        workspace_path=str(body.get("workspace_path") or "").strip(),
        max_concurrent_runs=max_runs,
        policy_overrides=resolved_overrides or None,
        policy_binding=policy_binding or None,
        retention_policy=retention_policy or None,
        execution_template=execution_template or None,
        environment_profile=environment_profile or None,
        project_id=str(body.get("project_id") or "").strip() or None,
    )
    return web.json_response(project, status=201)


async def handle_get_project(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    return web.json_response(project)


async def handle_update_project(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    body = await request.json() if request.can_read_body else {}
    if "max_concurrent_runs" in body:
        try:
            body["max_concurrent_runs"] = _parse_max_runs(body.get("max_concurrent_runs"))
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
    if "policy_overrides" in body:
        try:
            normalized_overrides = normalize_policy_overrides(body.get("policy_overrides") or {})
            body["policy_overrides"] = normalized_overrides
            if "policy_binding" not in body:
                body["policy_binding"] = normalized_overrides
        except (TypeError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=400)
    if "policy_binding" in body:
        try:
            normalized_binding = normalize_policy_overrides(body.get("policy_binding") or {})
            body["policy_binding"] = normalized_binding
            # Keep existing policy API aligned with explicit project-level policy binding.
            body["policy_overrides"] = normalized_binding
        except (TypeError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=400)
    if "retention_policy" in body:
        try:
            body["retention_policy"] = normalize_retention_policy(body.get("retention_policy") or {})
        except (TypeError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=400)
    if "execution_template" in body:
        try:
            body["execution_template"] = normalize_execution_template(body.get("execution_template") or {})
        except (TypeError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=400)
    if "environment_profile" in body:
        try:
            body["environment_profile"] = _normalize_environment_profile(body.get("environment_profile") or {})
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
    if "workspace_path" in body:
        raw_workspace = body.get("workspace_path")
        if raw_workspace is None:
            body["workspace_path"] = ""
        elif isinstance(raw_workspace, str):
            body["workspace_path"] = raw_workspace.strip()
        else:
            return web.json_response({"error": "workspace_path must be a string or null"}, status=400)
    project = manager.update_project(project_id, body)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    return web.json_response(project)


async def handle_get_project_policy(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    return web.json_response(resolve_effective_policy(project))


async def handle_update_project_policy(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    body = await request.json() if request.can_read_body else {}
    try:
        incoming = normalize_policy_overrides(body)
    except (TypeError, ValueError) as e:
        return web.json_response({"error": str(e)}, status=400)

    current = normalize_policy_overrides(project.get("policy_overrides") or {})
    for key in ("risk_tier", "retry_limit_per_stage", "budget_limit_usd_monthly"):
        if key in body:
            value = incoming.get(key)
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value
    updated = manager.update_project(
        project_id,
        {
            "policy_overrides": current or None,
            "policy_binding": current or None,
        },
    )
    if updated is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    return web.json_response(resolve_effective_policy(updated))


async def handle_get_project_execution_template(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    return web.json_response(resolve_execution_template(project))


async def handle_update_project_execution_template(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        return web.json_response({"error": "request body must be an object"}, status=400)

    updates: dict[str, object] = {}
    if "execution_template" in body:
        try:
            incoming_template = normalize_execution_template(
                body.get("execution_template"),
                allow_null_fields=True,
            )
        except (TypeError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=400)
        current_template = normalize_execution_template(project.get("execution_template") or {})
        for key in (
            "default_flow",
            "retry_policy",
            "github",
            "default_ref",
            "default_branch",
            "ref",
            "branch",
            "no_checks_policy",
        ):
            if key in incoming_template:
                value = incoming_template.get(key)
                if value is None:
                    current_template.pop(key, None)
                else:
                    current_template[key] = value
        updates["execution_template"] = current_template or None

    if "policy_binding" in body:
        try:
            binding = normalize_policy_overrides(body.get("policy_binding") or {})
        except (TypeError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=400)
        updates["policy_binding"] = binding or None
        # Keep effective policy API aligned with explicit execution binding.
        updates["policy_overrides"] = binding or None

    if not updates:
        return web.json_response({"error": "no supported fields to update"}, status=400)

    updated = manager.update_project(project_id, updates)
    if updated is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    return web.json_response(resolve_execution_template(updated))


async def handle_delete_project(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    force = request.query.get("force", "").lower() in {"1", "true", "yes"}
    ok, reason = manager.delete_project(project_id, force=force)
    if not ok:
        status = 409 if reason and "active sessions" in reason else 400
        return web.json_response({"error": reason or "delete failed"}, status=status)

    purged = {"tasks_removed": 0, "runs_removed": 0}
    for value in request.app.values():
        if isinstance(value, AutonomousPipelineStore):
            purged = value.delete_project_state(project_id)
            break
    return web.json_response({"deleted": project_id, "autonomous_purged": purged})


async def handle_get_project_retention(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    retention = resolve_retention_policy(project)
    effective = retention.get("effective", {})
    history_days = int(effective.get("history_days") or 30)
    min_sessions = int(effective.get("min_sessions_to_keep") or 20)
    live_ids = {s.id for s in manager.list_sessions(project_id=project_id)}
    plan = build_retention_plan(
        project_id=project_id,
        history_days=history_days,
        min_sessions_to_keep=min_sessions,
        live_session_ids=live_ids,
    )
    return web.json_response({**retention, "plan": plan})


async def handle_update_project_retention(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    body = await request.json() if request.can_read_body else {}
    try:
        incoming = normalize_retention_policy(body)
    except (TypeError, ValueError) as e:
        return web.json_response({"error": str(e)}, status=400)

    current = normalize_retention_policy(project.get("retention_policy") or {})
    for key in ("history_days", "min_sessions_to_keep", "archive_enabled", "archive_root"):
        if key in body:
            value = incoming.get(key)
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value
    updated = manager.update_project(project_id, {"retention_policy": current or None})
    if updated is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    return web.json_response(resolve_retention_policy(updated))


async def handle_apply_project_retention(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    retention = resolve_retention_policy(project)
    effective = retention.get("effective", {})
    try:
        history_days = int(body.get("history_days", effective.get("history_days", 30)))
        min_sessions = int(body.get("min_sessions_to_keep", effective.get("min_sessions_to_keep", 20)))
    except (TypeError, ValueError):
        return web.json_response(
            {"error": "history_days and min_sessions_to_keep must be integers"},
            status=400,
        )
    dry_run = bool(body.get("dry_run", True))
    archive_enabled = bool(body.get("archive_enabled", effective.get("archive_enabled", True)))
    archive_root = str(body.get("archive_root") or effective.get("archive_root") or "").strip()
    if not archive_root:
        return web.json_response({"error": "archive_root cannot be empty"}, status=400)

    live_ids = {s.id for s in manager.list_sessions(project_id=project_id)}
    plan = build_retention_plan(
        project_id=project_id,
        history_days=history_days,
        min_sessions_to_keep=min_sessions,
        live_session_ids=live_ids,
    )
    if dry_run:
        return web.json_response({"dry_run": True, "policy": retention, "plan": plan})
    applied = apply_retention_plan(
        project_id=project_id,
        candidates=plan.get("candidates", []),
        archive_enabled=archive_enabled,
        archive_root=archive_root,
    )
    return web.json_response({"dry_run": False, "policy": retention, "plan": plan, "applied": applied})


async def handle_project_onboarding(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    template_id = str(body.get("template_id") or "").strip()
    template = None
    if template_id:
        template = get_project_template(template_id)
        if template is None:
            return web.json_response({"error": f"Unknown project template: {template_id}"}, status=400)

    repository = str(body.get("repository") or project.get("repository") or "").strip()
    if not repository:
        return web.json_response(
            {"error": "repository is required (or set repository on the project first)"},
            status=400,
        )
    commands_from_template = template.get("commands") if isinstance(template, dict) else None
    commands_from_body = body.get("commands") if isinstance(body.get("commands"), dict) else None
    merged_commands: dict[str, str] | None = None
    if isinstance(commands_from_template, dict):
        merged_commands = {
            str(k): str(v)
            for k, v in commands_from_template.items()
            if isinstance(k, str) and isinstance(v, str)
        }
    if isinstance(commands_from_body, dict):
        if merged_commands is None:
            merged_commands = {}
        for key, value in commands_from_body.items():
            if isinstance(key, str) and isinstance(value, str):
                merged_commands[key] = value

    template_checks = template.get("required_checks") if isinstance(template, dict) else None
    body_checks = body.get("required_checks")
    resolved_checks = (
        [str(x).strip() for x in body_checks if str(x).strip()]
        if isinstance(body_checks, list)
        else (
            [str(x).strip() for x in template_checks if str(x).strip()]
            if isinstance(template_checks, list)
            else None
        )
    )

    try:
        report = run_project_onboarding(
            project_id=project_id,
            repository=repository,
            workspace_path=str(body.get("workspace_path") or "").strip() or None,
            stack=str(body.get("stack") or (template.get("stack") if isinstance(template, dict) else "node")).strip() or "node",
            repo_type=str(body.get("repo_type") or (template.get("repo_type") if isinstance(template, dict) else "single")).strip() or "single",
            create_manifest=bool(body.get("create_manifest", True)),
            force_manifest=bool(body.get("force_manifest", False)),
            dry_run=bool(body.get("dry_run", True)),
            dry_run_command=str(body.get("dry_run_command") or (template.get("dry_run_command") if isinstance(template, dict) else "")).strip() or None,
            command_overrides=merged_commands or None,
            required_checks=resolved_checks,
        )
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    updates: dict[str, object] = {"repository": repository}
    resolved_workspace = str(report.get("workspace_path") or "").strip()
    if resolved_workspace:
        updates["workspace_path"] = resolved_workspace
    manager.update_project(project_id, updates)
    return web.json_response(report, status=200 if report.get("ready") else 202)


async def handle_project_repository_provision(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        return web.json_response({"error": "request body must be an object"}, status=400)

    name = str(body.get("name") or "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    if not _GITHUB_REPO_NAME_RE.fullmatch(name):
        return web.json_response({"error": "name contains unsupported characters"}, status=400)

    owner_raw = body.get("owner")
    owner = ""
    if owner_raw is not None:
        owner = str(owner_raw).strip()
        if owner and not re.fullmatch(r"[A-Za-z0-9_.-]+", owner):
            return web.json_response({"error": "owner must be a GitHub user/org slug"}, status=400)

    visibility = str(body.get("visibility") or "private").strip().lower()
    if visibility not in {"private", "public", "internal"}:
        return web.json_response(
            {"error": "visibility must be one of: private, public, internal"},
            status=400,
        )

    initialize_readme = body.get("initialize_readme", True)
    if not isinstance(initialize_readme, bool):
        return web.json_response({"error": "initialize_readme must be a boolean"}, status=400)
    description = str(body.get("description") or "").strip()

    token = _resolve_github_token(request)
    if not token:
        return web.json_response(
            {"error": "GitHub token is not configured (set credential 'github' or GITHUB_TOKEN)"},
            status=400,
        )

    try:
        created = await asyncio.to_thread(
            _github_create_repository,
            token=token,
            name=name,
            owner=owner or None,
            visibility=visibility,
            description=description,
            initialize_readme=initialize_readme,
        )
    except _GitHubProvisionError as e:
        return web.json_response({"error": str(e)}, status=e.status)

    full_name = str(created.get("full_name") or "").strip()
    html_url = str(created.get("html_url") or "").strip()
    clone_url = str(created.get("clone_url") or "").strip()
    ssh_url = str(created.get("ssh_url") or "").strip()
    default_branch = str(created.get("default_branch") or "").strip()
    visibility_out = str(created.get("visibility") or visibility).strip().lower() or visibility
    repository_binding = html_url or full_name
    updates: dict[str, object] = {}
    if repository_binding:
        updates["repository"] = repository_binding
    updated_project = manager.update_project(project_id, updates) if updates else project

    return web.json_response(
        {
            "project_id": project_id,
            "repository": {
                "name": str(created.get("name") or name),
                "full_name": full_name,
                "html_url": html_url,
                "clone_url": clone_url,
                "ssh_url": ssh_url,
                "default_branch": default_branch,
                "visibility": visibility_out,
                "private": bool(created.get("private", visibility_out != "public")),
            },
            "project": updated_project if isinstance(updated_project, dict) else project,
        },
        status=201,
    )


async def handle_project_repository_bind(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        return web.json_response({"error": "request body must be an object"}, status=400)
    repository_raw = str(body.get("repository") or "").strip()
    if not repository_raw:
        return web.json_response({"error": "repository is required"}, status=400)
    repository_slug = _normalize_github_repository(repository_raw)
    if not repository_slug:
        return web.json_response(
            {"error": "repository must be in owner/name format or GitHub URL"},
            status=400,
        )

    token = _resolve_github_token(request)
    if not token:
        return web.json_response(
            {"error": "GitHub token is not configured (set credential 'github' or GITHUB_TOKEN)"},
            status=400,
        )

    try:
        repo_data = await asyncio.to_thread(
            _github_get_repository,
            token=token,
            repository=repository_slug,
        )
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    except _GitHubProvisionError as e:
        return web.json_response({"error": str(e)}, status=e.status)

    html_url = str(repo_data.get("html_url") or "").strip()
    full_name = str(repo_data.get("full_name") or repository_slug).strip()
    repository_binding = html_url or full_name
    updated = manager.update_project(project_id, {"repository": repository_binding})
    return web.json_response(
        {
            "project_id": project_id,
            "repository": {
                "full_name": full_name,
                "html_url": html_url,
                "private": bool(repo_data.get("private", False)),
                "default_branch": str(repo_data.get("default_branch") or "").strip(),
                "visibility": str(repo_data.get("visibility") or "").strip(),
            },
            "project": updated if isinstance(updated, dict) else project,
        }
    )


async def handle_get_project_environment(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    profile = project.get("environment_profile")
    profile = profile if isinstance(profile, dict) else {}
    return web.json_response({"project_id": project_id, "environment_profile": profile})


async def handle_update_project_environment(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        return web.json_response({"error": "request body must be an object"}, status=400)
    raw = body.get("environment_profile") if "environment_profile" in body else body
    try:
        profile = _normalize_environment_profile(raw or {})
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    updated = manager.update_project(project_id, {"environment_profile": profile or None})
    if updated is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    return web.json_response(
        {
            "project_id": project_id,
            "environment_profile": updated.get("environment_profile") if isinstance(updated, dict) else {},
        }
    )


async def handle_project_environment_preflight(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    profile = project.get("environment_profile")
    profile = profile if isinstance(profile, dict) else {}
    credential_store = request.app.get(APP_KEY_CREDENTIAL_STORE)
    if credential_store is None:
        return web.json_response({"error": "Credential store is not initialized"}, status=500)
    report = _environment_preflight(profile=profile, credential_store=credential_store)
    return web.json_response(
        {
            "project_id": project_id,
            "environment_profile": profile,
            "preflight": report,
        },
        status=200 if bool(report.get("ready")) else 202,
    )


async def handle_project_sessions(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    if manager.get_project(project_id) is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    sessions = manager.list_sessions(project_id=project_id)
    data = []
    for s in sessions:
        data.append(
            {
                "session_id": s.id,
                "project_id": s.project_id,
                "graph_id": s.graph_id,
                "has_worker": s.graph_runtime is not None,
                "loaded_at": s.loaded_at,
                "agent_path": str(s.worker_path) if s.worker_path else "",
            }
        )
    return web.json_response({"sessions": data})


async def handle_project_metrics(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    if manager.get_project(project_id) is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    active_sessions = len(manager.list_sessions(project_id=project_id))
    return web.json_response(
        compute_project_metrics(project_id=project_id, active_sessions=active_sessions)
    )


async def handle_get_project_toolchain_profile(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)
    profile = project.get("toolchain_profile")
    return web.json_response(
        {
            "project_id": project_id,
            "toolchain_profile": profile if isinstance(profile, dict) else {},
        }
    )


async def handle_plan_project_toolchain_profile(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        return web.json_response({"error": "request body must be an object"}, status=400)
    try:
        source = resolve_toolchain_source(project, body)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    try:
        plan = await asyncio.to_thread(
            detect_toolchain_plan,
            workspace_path=source.get("workspace_path"),
            repository=source.get("repository"),
        )
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    except RuntimeError as e:
        return web.json_response({"error": str(e)}, status=502)

    pending = {
        "source": source,
        "plan": plan,
    }
    profile = project.get("toolchain_profile")
    updated_profile: dict[str, object] = dict(profile) if isinstance(profile, dict) else {}
    updated_profile["pending_plan"] = pending
    updated_profile["last_plan"] = pending
    updated_profile["updated_at"] = time.time()
    manager.update_project(project_id, {"toolchain_profile": updated_profile})

    commands = build_apply_commands(
        workspace_path=source.get("workspace_path"),
        repository=source.get("repository"),
        confirm_token=str(plan.get("confirm_token") or ""),
    )
    return web.json_response(
        {
            "project_id": project_id,
            "pending_plan": pending,
            "instructions": {
                **commands,
                "env_exports": build_env_exports(plan),
            },
        }
    )


async def handle_approve_project_toolchain_profile(request: web.Request) -> web.Response:
    manager = _get_manager(request)
    project_id = request.match_info["project_id"]
    project = manager.get_project(project_id)
    if project is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        return web.json_response({"error": "request body must be an object"}, status=400)
    confirm_token = str(body.get("confirm_token") or "").strip()
    if not confirm_token:
        return web.json_response({"error": "confirm_token is required"}, status=400)
    revalidate = bool(body.get("revalidate", True))

    profile = project.get("toolchain_profile")
    profile_dict: dict[str, object] = dict(profile) if isinstance(profile, dict) else {}
    pending = profile_dict.get("pending_plan")
    if not isinstance(pending, dict):
        return web.json_response(
            {"error": "no pending toolchain plan; call plan endpoint first"},
            status=409,
        )
    source = pending.get("source")
    plan = pending.get("plan")
    if not isinstance(source, dict) or not isinstance(plan, dict):
        return web.json_response(
            {"error": "pending toolchain plan is corrupted; regenerate plan"},
            status=409,
        )
    expected_token = str(plan.get("confirm_token") or "").strip()
    if not expected_token:
        return web.json_response(
            {"error": "pending toolchain plan has no confirm token; regenerate plan"},
            status=409,
        )
    if confirm_token != expected_token:
        return web.json_response(
            {
                "error": "confirm_token mismatch",
                "plan_fingerprint": plan.get("plan_fingerprint"),
            },
            status=409,
        )

    if revalidate:
        try:
            current_plan = await asyncio.to_thread(
                detect_toolchain_plan,
                workspace_path=(
                    str(source.get("workspace_path") or "").strip() or None
                    if isinstance(source, dict)
                    else None
                ),
                repository=(
                    str(source.get("repository") or "").strip() or None
                    if isinstance(source, dict)
                    else None
                ),
            )
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
        except RuntimeError as e:
            return web.json_response({"error": str(e)}, status=502)
        if str(current_plan.get("confirm_token") or "") != expected_token:
            refreshed_pending = {
                "source": source,
                "plan": current_plan,
            }
            profile_dict["pending_plan"] = refreshed_pending
            profile_dict["last_plan"] = refreshed_pending
            profile_dict["updated_at"] = time.time()
            manager.update_project(project_id, {"toolchain_profile": profile_dict})
            return web.json_response(
                {
                    "error": "toolchain plan changed; review updated plan and confirm again",
                    "pending_plan": refreshed_pending,
                },
                status=409,
            )

    approved = {
        "source": source,
        "plan": plan,
        "approved_at": time.time(),
        "approved_token": confirm_token,
    }
    profile_dict["approved_plan"] = approved
    profile_dict["pending_plan"] = None
    profile_dict["updated_at"] = time.time()
    ws_update = str(source.get("workspace_path") or "").strip()
    updates: dict[str, object] = {"toolchain_profile": profile_dict}
    if ws_update:
        updates["workspace_path"] = ws_update
    manager.update_project(project_id, updates)
    commands = build_apply_commands(
        workspace_path=str(source.get("workspace_path") or "").strip() or None,
        repository=str(source.get("repository") or "").strip() or None,
        confirm_token=confirm_token,
    )
    return web.json_response(
        {
            "project_id": project_id,
            "status": "approved",
            "approved_plan": approved,
            "instructions": {
                **commands,
                "env_exports": build_env_exports(plan),
            },
        }
    )


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/projects", handle_list_projects)
    app.router.add_get("/api/projects/metrics", handle_projects_metrics)
    app.router.add_get("/api/projects/templates", handle_project_templates)
    app.router.add_post("/api/projects", handle_create_project)
    app.router.add_get("/api/projects/{project_id}", handle_get_project)
    app.router.add_patch("/api/projects/{project_id}", handle_update_project)
    app.router.add_delete("/api/projects/{project_id}", handle_delete_project)
    app.router.add_get("/api/projects/{project_id}/sessions", handle_project_sessions)
    app.router.add_get("/api/projects/{project_id}/metrics", handle_project_metrics)
    app.router.add_get("/api/projects/{project_id}/environment", handle_get_project_environment)
    app.router.add_patch("/api/projects/{project_id}/environment", handle_update_project_environment)
    app.router.add_post("/api/projects/{project_id}/environment/preflight", handle_project_environment_preflight)
    app.router.add_get("/api/projects/{project_id}/toolchain-profile", handle_get_project_toolchain_profile)
    app.router.add_post("/api/projects/{project_id}/toolchain-profile/plan", handle_plan_project_toolchain_profile)
    app.router.add_post(
        "/api/projects/{project_id}/toolchain-profile/approve",
        handle_approve_project_toolchain_profile,
    )
    app.router.add_get("/api/projects/{project_id}/policy", handle_get_project_policy)
    app.router.add_patch("/api/projects/{project_id}/policy", handle_update_project_policy)
    app.router.add_get("/api/projects/{project_id}/execution-template", handle_get_project_execution_template)
    app.router.add_patch("/api/projects/{project_id}/execution-template", handle_update_project_execution_template)
    app.router.add_get("/api/projects/{project_id}/retention", handle_get_project_retention)
    app.router.add_patch("/api/projects/{project_id}/retention", handle_update_project_retention)
    app.router.add_post("/api/projects/{project_id}/retention/apply", handle_apply_project_retention)
    app.router.add_post("/api/projects/{project_id}/onboarding", handle_project_onboarding)
    app.router.add_post("/api/projects/{project_id}/repository/bind", handle_project_repository_bind)
    app.router.add_post("/api/projects/{project_id}/repository/provision", handle_project_repository_provision)

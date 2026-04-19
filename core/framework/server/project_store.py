"""Persistent project registry for grouping Hive sessions."""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class Project:
    """Project metadata used to scope and organize sessions."""

    id: str
    name: str
    description: str = ""
    repository: str = ""
    workspace_path: str = ""
    max_concurrent_runs: int | None = None
    policy_overrides: dict[str, Any] | None = None
    policy_binding: dict[str, Any] | None = None
    retention_policy: dict[str, Any] | None = None
    execution_template: dict[str, Any] | None = None
    toolchain_profile: dict[str, Any] | None = None
    environment_profile: dict[str, Any] | None = None
    created_at: float = 0.0
    updated_at: float = 0.0


class ProjectStore:
    """Simple JSON-backed project registry under ``~/.hive/server``."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (Path.home() / ".hive" / "server" / "projects.json")
        self._projects: dict[str, Project] = {}
        self._load()

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug[:48] or f"project-{uuid.uuid4().hex[:8]}"

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            items = raw.get("projects", [])
            for item in items:
                try:
                    project = Project(**item)
                except TypeError:
                    continue
                self._projects[project.id] = project
        except (OSError, json.JSONDecodeError):
            return

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "projects": [asdict(p) for p in sorted(self._projects.values(), key=lambda x: x.created_at)],
        }
        self._path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def ensure_project(self, project_id: str, *, name: str, description: str = "") -> Project:
        existing = self._projects.get(project_id)
        if existing is not None:
            return existing
        now = time.time()
        project = Project(
            id=project_id,
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
        )
        self._projects[project_id] = project
        self._save()
        return project

    def list_projects(self) -> list[Project]:
        return sorted(self._projects.values(), key=lambda p: (p.updated_at, p.created_at), reverse=True)

    def get_project(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)

    def create_project(
        self,
        *,
        name: str,
        description: str = "",
        repository: str = "",
        workspace_path: str = "",
        max_concurrent_runs: int | None = None,
        policy_overrides: dict[str, Any] | None = None,
        policy_binding: dict[str, Any] | None = None,
        retention_policy: dict[str, Any] | None = None,
        execution_template: dict[str, Any] | None = None,
        toolchain_profile: dict[str, Any] | None = None,
        environment_profile: dict[str, Any] | None = None,
        project_id: str | None = None,
    ) -> Project:
        now = time.time()
        candidate = (project_id or self._slugify(name)).strip()
        if not candidate:
            candidate = f"project-{uuid.uuid4().hex[:8]}"
        if candidate in self._projects:
            candidate = f"{candidate}-{uuid.uuid4().hex[:6]}"
        project = Project(
            id=candidate,
            name=name.strip() or candidate,
            description=description.strip(),
            repository=repository.strip(),
            workspace_path=workspace_path.strip(),
            max_concurrent_runs=max_concurrent_runs if max_concurrent_runs and max_concurrent_runs > 0 else None,
            policy_overrides=policy_overrides or None,
            policy_binding=policy_binding or None,
            retention_policy=retention_policy or None,
            execution_template=execution_template or None,
            toolchain_profile=toolchain_profile or None,
            environment_profile=environment_profile or None,
            created_at=now,
            updated_at=now,
        )
        self._projects[project.id] = project
        self._save()
        return project

    def update_project(self, project_id: str, updates: dict[str, Any]) -> Project | None:
        project = self._projects.get(project_id)
        if project is None:
            return None
        if "name" in updates and isinstance(updates["name"], str):
            project.name = updates["name"].strip() or project.name
        if "description" in updates and isinstance(updates["description"], str):
            project.description = updates["description"].strip()
        if "repository" in updates and isinstance(updates["repository"], str):
            project.repository = updates["repository"].strip()
        if "workspace_path" in updates:
            raw_ws = updates.get("workspace_path")
            if raw_ws is None:
                project.workspace_path = ""
            elif isinstance(raw_ws, str):
                project.workspace_path = raw_ws.strip()
        if "max_concurrent_runs" in updates:
            raw = updates.get("max_concurrent_runs")
            if raw is None or raw == "":
                project.max_concurrent_runs = None
            else:
                try:
                    value = int(raw)
                except (TypeError, ValueError):
                    value = project.max_concurrent_runs or 1
                project.max_concurrent_runs = value if value > 0 else 1
        if "policy_overrides" in updates:
            val = updates["policy_overrides"]
            if val is None or isinstance(val, dict):
                project.policy_overrides = val or None
        if "policy_binding" in updates:
            val = updates["policy_binding"]
            if val is None or isinstance(val, dict):
                project.policy_binding = val or None
        if "retention_policy" in updates:
            val = updates["retention_policy"]
            if val is None or isinstance(val, dict):
                project.retention_policy = val or None
        if "execution_template" in updates:
            val = updates["execution_template"]
            if val is None or isinstance(val, dict):
                project.execution_template = val or None
        if "toolchain_profile" in updates:
            val = updates["toolchain_profile"]
            if val is None or isinstance(val, dict):
                project.toolchain_profile = val or None
        if "environment_profile" in updates:
            val = updates["environment_profile"]
            if val is None or isinstance(val, dict):
                project.environment_profile = val or None
        project.updated_at = time.time()
        self._save()
        return project

    def delete_project(self, project_id: str) -> bool:
        if project_id not in self._projects:
            return False
        del self._projects[project_id]
        self._save()
        return True

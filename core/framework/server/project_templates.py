"""Project onboarding template catalog."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "frontend-web",
        "name": "Frontend Web App",
        "description": "SPA/web UI profile with CI-ready frontend checks.",
        "stack": "node",
        "repo_type": "single",
        "required_checks": ["lint", "typecheck", "test", "build", "smoke"],
        "commands": {
            "install": "if [ -f package-lock.json ]; then npm ci; else npm install; fi",
            "lint": "npm run lint:ci",
            "typecheck": "npm run typecheck",
            "test": "npm run test:ci",
            "build": "npm run build",
            "smoke": "npm run smoke",
        },
        "dry_run_command": "test -f automation/hive.manifest.yaml",
    },
    {
        "id": "backend-python-api",
        "name": "Backend Python API",
        "description": "Python service profile with uv + strict typing checks.",
        "stack": "python",
        "repo_type": "single",
        "required_checks": ["lint", "typecheck", "test", "build"],
        "commands": {
            "install": "uv sync",
            "lint": "uv run ruff check .",
            "typecheck": "uv run pyright",
            "test": "uv run pytest",
            "build": "python -m compileall -q .",
            "smoke": "uv run pytest -m smoke",
        },
        "dry_run_command": "test -f automation/hive.manifest.yaml",
    },
    {
        "id": "fullstack-platform",
        "name": "Fullstack Platform",
        "description": "Combined frontend/backend profile for mono-service fullstack apps.",
        "stack": "fullstack",
        "repo_type": "single",
        "required_checks": ["lint", "typecheck", "test", "build", "smoke"],
        "commands": {
            "install": "if [ -f package-lock.json ]; then npm ci; else npm install; fi",
            "lint": "npm run lint",
            "typecheck": "npm run typecheck",
            "test": "npm run test:ci",
            "build": "npm run build",
            "smoke": "npm run smoke:e2e",
        },
        "dry_run_command": "test -f automation/hive.manifest.yaml",
    },
]


def list_project_templates() -> list[dict[str, Any]]:
    return deepcopy(_TEMPLATES)


def get_project_template(template_id: str) -> dict[str, Any] | None:
    tid = (template_id or "").strip()
    if not tid:
        return None
    for template in _TEMPLATES:
        if template["id"] == tid:
            return deepcopy(template)
    return None

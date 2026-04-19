# Overlap Batch A Focus Patch Summary

- Generated: 2026-04-18T00:15:34.006094+00:00
- Target ref: `origin/main`
- Focus patch: `docs/ops/upstream-migration/overlap-batch-a-focus-latest.patch`
- Matched files: 6
- Matched hunks: 43

## Keywords

- `from typing import Any`
- `def create_app(model: str | None = None, model_profile: str | None = None)`
- `model_profile=model_profile`
- `APP_KEY_MANAGER`
- `APP_KEY_CREDENTIAL_STORE`
- `APP_KEY_TELEGRAM_BRIDGE`
- `register_autonomous_routes`
- `register_project_routes`
- `/api/telegram/bridge/status`
- `APP_KEY_PROJECT_EXEC_`
- `/api/projects/{project_id}/queue`
- `project_id = body.get("project_id")`
- `manager.list_sessions(project_id=project_id)`
- `/api/agents`
- `/api/sessions/{session_id}/reveal`
- `/api/sessions/{session_id}/graph`
- `_project_workspace_from_metadata`
- `session.project_id`
- `APP_KEY_AUTONOMOUS_STORE`

## Matched Files

- `core/framework/server/app.py`
- `core/framework/server/queen_orchestrator.py`
- `core/framework/server/routes_credentials.py`
- `core/framework/server/routes_execution.py`
- `core/framework/server/routes_sessions.py`
- `core/framework/server/session_manager.py`

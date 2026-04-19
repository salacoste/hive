from __future__ import annotations

from pathlib import Path

from framework.server.queen_orchestrator import (
    _patch_mcp_server_list_for_workspace,
    _project_workspace_from_metadata,
)


def test_project_workspace_from_metadata_prefers_direct_path(tmp_path: Path) -> None:
    direct = tmp_path / "direct-workspace"
    direct.mkdir(parents=True, exist_ok=True)
    approved = tmp_path / "approved-workspace"
    approved.mkdir(parents=True, exist_ok=True)

    project = {
        "workspace_path": str(direct),
        "toolchain_profile": {
            "approved_plan": {
                "source": {"workspace_path": str(approved)},
            }
        },
    }
    resolved = _project_workspace_from_metadata(project)
    assert resolved == str(direct.resolve())


def test_project_workspace_from_metadata_falls_back_to_approved_plan(tmp_path: Path) -> None:
    approved = tmp_path / "approved-workspace"
    approved.mkdir(parents=True, exist_ok=True)
    project = {
        "toolchain_profile": {
            "approved_plan": {
                "source": {"workspace_path": str(approved)},
            }
        },
    }
    resolved = _project_workspace_from_metadata(project)
    assert resolved == str(approved.resolve())


def test_patch_mcp_server_list_for_workspace_adds_coder_tools_env(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    servers = [
        {"name": "coder-tools", "env": {"EXISTING": "1"}},
        {"name": "hive-tools"},
    ]
    patched = _patch_mcp_server_list_for_workspace(
        server_list=servers,
        allow_paths=[str(ws.resolve())],
    )
    coder = next(item for item in patched if item.get("name") == "coder-tools")
    assert "CODER_TOOLS_ALLOWED_PATHS" in (coder.get("env") or {})
    assert str(ws.resolve()) in str((coder.get("env") or {}).get("CODER_TOOLS_ALLOWED_PATHS", ""))

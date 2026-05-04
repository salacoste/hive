from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from framework.server.queen_orchestrator import (
    _hydrate_queen_identity_prompt,
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


def test_hydrate_queen_identity_prompt_populates_phase_state(monkeypatch) -> None:
    from framework.agents.queen import queen_profiles

    profile = {
        "name": "Alexandra",
        "title": "Head of Technology",
        "core_traits": "Builder-first technical operator.",
    }

    monkeypatch.setattr(queen_profiles, "ensure_default_queens", lambda: None)
    monkeypatch.setattr(queen_profiles, "load_queen_profile", lambda queen_id: profile)
    monkeypatch.setattr(
        queen_profiles,
        "format_queen_identity_prompt",
        lambda p, max_examples=1: "<core_identity>Alexandra, Head of Technology</core_identity>",
    )

    session = SimpleNamespace(queen_name="queen_technology")
    phase_state = SimpleNamespace(queen_profile=None, queen_identity_prompt="")
    _hydrate_queen_identity_prompt(session=session, phase_state=phase_state)

    assert phase_state.queen_profile == profile
    assert "<core_identity>" in phase_state.queen_identity_prompt
    assert "Head of Technology" in phase_state.queen_identity_prompt


def test_hydrate_queen_identity_prompt_uses_default_queen_when_missing(monkeypatch) -> None:
    from framework.agents.queen import queen_profiles

    captured: dict[str, str] = {}

    monkeypatch.setattr(queen_profiles, "ensure_default_queens", lambda: None)

    def _load(queen_id: str):
        captured["queen_id"] = queen_id
        return {"name": "Alexandra", "title": "Head of Technology", "core_traits": "x"}

    monkeypatch.setattr(queen_profiles, "load_queen_profile", _load)
    monkeypatch.setattr(
        queen_profiles,
        "format_queen_identity_prompt",
        lambda p, max_examples=1: "<core_identity>ok</core_identity>",
    )

    session = SimpleNamespace(queen_name=None)
    phase_state = SimpleNamespace(queen_profile=None, queen_identity_prompt="")
    _hydrate_queen_identity_prompt(session=session, phase_state=phase_state)

    assert captured["queen_id"] == "queen_technology"
    assert "<core_identity>" in phase_state.queen_identity_prompt

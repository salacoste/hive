from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path


def _load_coder_tools_server():
    module_path = Path(__file__).resolve().parents[1] / "coder_tools_server.py"
    spec = importlib.util.spec_from_file_location("coder_tools_server_under_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install_fake_framework(monkeypatch, tools_by_server: dict[str, list[dict]]) -> None:
    framework_mod = types.ModuleType("framework")
    loader_mod = types.ModuleType("framework.loader")
    mcp_client_mod = types.ModuleType("framework.loader.mcp_client")
    tool_registry_mod = types.ModuleType("framework.loader.tool_registry")

    class FakeMCPServerConfig:
        def __init__(self, **kwargs):
            self.name = kwargs.get("name", "")

    class FakeTool:
        def __init__(self, name: str, description: str = "", input_schema: dict | None = None):
            self.name = name
            self.description = description
            self.input_schema = input_schema or {}

    class FakeMCPClient:
        def __init__(self, config):
            self._server_name = config.name

        def connect(self):
            return None

        def list_tools(self):
            items = tools_by_server.get(self._server_name, [])
            return [
                FakeTool(
                    name=item["name"],
                    description=item.get("description", ""),
                    input_schema=item.get("input_schema", {}),
                )
                for item in items
            ]

        def disconnect(self):
            return None

    class FakeToolRegistry:
        @staticmethod
        def resolve_mcp_stdio_config(config: dict, _config_dir: Path) -> dict:
            return config

    mcp_client_mod.MCPClient = FakeMCPClient
    mcp_client_mod.MCPServerConfig = FakeMCPServerConfig
    tool_registry_mod.ToolRegistry = FakeToolRegistry

    framework_mod.loader = loader_mod
    loader_mod.mcp_client = mcp_client_mod
    loader_mod.tool_registry = tool_registry_mod

    monkeypatch.setitem(sys.modules, "framework", framework_mod)
    monkeypatch.setitem(sys.modules, "framework.loader", loader_mod)
    monkeypatch.setitem(sys.modules, "framework.loader.mcp_client", mcp_client_mod)
    monkeypatch.setitem(sys.modules, "framework.loader.tool_registry", tool_registry_mod)


def _call_list_agent_tools(mod, **kwargs) -> str:
    tool = mod.mcp._tool_manager._tools["list_agent_tools"]
    return tool.fn(**kwargs)


def test_list_agent_tools_groups_by_provider_and_keeps_uncredentialed(monkeypatch, tmp_path):
    _install_fake_framework(
        monkeypatch,
        tools_by_server={
            "fake-server": [
                {"name": "gmail_list_messages", "description": "Read Gmail"},
                {"name": "calendar_list_events", "description": "Read calendar"},
                {"name": "send_email", "description": "Send email"},
                {"name": "web_scrape", "description": "Scrape a page"},
            ]
        },
    )
    mod = _load_coder_tools_server()
    mod.PROJECT_ROOT = str(tmp_path)

    config_path = tmp_path / "mcp_servers.json"
    config_path.write_text(
        json.dumps({"fake-server": {"transport": "stdio", "command": "noop", "args": []}}),
        encoding="utf-8",
    )

    raw = _call_list_agent_tools(
        mod,
        server_config_path="mcp_servers.json",
        output_schema="simple",
        group="all",
    )
    data = json.loads(raw)

    providers = data["tools_by_provider"]
    assert "google" in providers
    assert "resend" in providers
    assert "no_provider" in providers

    google_tools = {t["name"] for t in providers["google"]["tools"]}
    assert "gmail_list_messages" in google_tools
    assert "calendar_list_events" in google_tools
    assert "send_email" in google_tools
    assert providers["google"]["authorization"]

    resend_tools = {t["name"] for t in providers["resend"]["tools"]}
    assert resend_tools == {"send_email"}
    assert providers["resend"]["authorization"]

    no_provider_tools = {t["name"] for t in providers["no_provider"]["tools"]}
    assert "web_scrape" in no_provider_tools
    assert providers["no_provider"]["authorization"] == {}


def test_list_agent_tools_provider_filter_and_legacy_prefix_filter(monkeypatch, tmp_path):
    _install_fake_framework(
        monkeypatch,
        tools_by_server={
            "fake-server": [
                {"name": "gmail_list_messages", "description": "Read Gmail"},
                {"name": "web_scrape", "description": "Scrape a page"},
            ]
        },
    )
    mod = _load_coder_tools_server()
    mod.PROJECT_ROOT = str(tmp_path)

    config_path = tmp_path / "mcp_servers.json"
    config_path.write_text(
        json.dumps({"fake-server": {"transport": "stdio", "command": "noop", "args": []}}),
        encoding="utf-8",
    )

    provider_raw = _call_list_agent_tools(
        mod,
        server_config_path="mcp_servers.json",
        output_schema="simple",
        group="google",
    )
    provider_data = json.loads(provider_raw)
    assert list(provider_data["tools_by_provider"].keys()) == ["google"]
    assert provider_data["all_tool_names"] == ["gmail_list_messages"]

    legacy_raw = _call_list_agent_tools(
        mod,
        server_config_path="mcp_servers.json",
        output_schema="simple",
        group="gmail",
    )
    legacy_data = json.loads(legacy_raw)
    assert list(legacy_data["tools_by_provider"].keys()) == ["google"]
    assert legacy_data["all_tool_names"] == ["gmail_list_messages"]


def test_list_agent_tools_summary_all_reports_credentials_status(monkeypatch, tmp_path):
    _install_fake_framework(
        monkeypatch,
        tools_by_server={
            "fake-server": [
                {"name": "gmail_list_messages", "description": "Read Gmail"},
                {"name": "send_email", "description": "Send email"},
                {"name": "slack_send_message", "description": "Send Slack message"},
            ]
        },
    )
    mod = _load_coder_tools_server()
    mod.PROJECT_ROOT = str(tmp_path)

    config_path = tmp_path / "mcp_servers.json"
    config_path.write_text(
        json.dumps({"fake-server": {"transport": "stdio", "command": "noop", "args": []}}),
        encoding="utf-8",
    )

    monkeypatch.setenv("GOOGLE_ACCESS_TOKEN", "test-google")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)

    raw = _call_list_agent_tools(
        mod,
        server_config_path="mcp_servers.json",
        output_schema="summary",
        group="all",
    )
    data = json.loads(raw)
    providers = data["providers"]

    assert "google" in providers
    assert providers["google"]["credentials_required"] == ["google"]
    assert providers["google"]["credentials_available"] is True

    assert "resend" in providers
    assert providers["resend"]["credentials_required"] == ["resend"]
    assert providers["resend"]["credentials_available"] is False

    assert "slack" in providers
    assert providers["slack"]["credentials_required"] == ["slack"]
    assert providers["slack"]["credentials_available"] is False


def test_list_agent_tools_available_filter_supports_multi_provider_tools(monkeypatch, tmp_path):
    _install_fake_framework(
        monkeypatch,
        tools_by_server={
            "fake-server": [
                {"name": "send_email", "description": "Send email"},
                {"name": "web_scrape", "description": "Scrape a page"},
            ]
        },
    )
    mod = _load_coder_tools_server()
    mod.PROJECT_ROOT = str(tmp_path)

    config_path = tmp_path / "mcp_servers.json"
    config_path.write_text(
        json.dumps({"fake-server": {"transport": "stdio", "command": "noop", "args": []}}),
        encoding="utf-8",
    )

    monkeypatch.setenv("GOOGLE_ACCESS_TOKEN", "test-google")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    available_raw = _call_list_agent_tools(
        mod,
        server_config_path="mcp_servers.json",
        output_schema="names",
        credentials="available",
    )
    available = json.loads(available_raw)
    available_names = set()
    for provider in available["tools_by_provider"].values():
        available_names.update(provider["tool_names"])
    assert "send_email" in available_names

    unavailable_raw = _call_list_agent_tools(
        mod,
        server_config_path="mcp_servers.json",
        output_schema="names",
        credentials="unavailable",
    )
    unavailable = json.loads(unavailable_raw)
    unavailable_names = set()
    for provider in unavailable["tools_by_provider"].values():
        unavailable_names.update(provider["tool_names"])
    assert "send_email" not in unavailable_names


def test_list_agent_tools_multi_provider_tool_unavailable_when_no_provider_creds(
    monkeypatch, tmp_path
):
    _install_fake_framework(
        monkeypatch,
        tools_by_server={
            "fake-server": [
                {"name": "send_email", "description": "Send email"},
            ]
        },
    )
    mod = _load_coder_tools_server()
    mod.PROJECT_ROOT = str(tmp_path)

    config_path = tmp_path / "mcp_servers.json"
    config_path.write_text(
        json.dumps({"fake-server": {"transport": "stdio", "command": "noop", "args": []}}),
        encoding="utf-8",
    )

    monkeypatch.delenv("GOOGLE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    available_raw = _call_list_agent_tools(
        mod,
        server_config_path="mcp_servers.json",
        output_schema="names",
        credentials="available",
    )
    available = json.loads(available_raw)
    available_names = set()
    for provider in available["tools_by_provider"].values():
        available_names.update(provider["tool_names"])
    assert "send_email" not in available_names

    unavailable_raw = _call_list_agent_tools(
        mod,
        server_config_path="mcp_servers.json",
        output_schema="names",
        credentials="unavailable",
    )
    unavailable = json.loads(unavailable_raw)
    unavailable_names = set()
    for provider in unavailable["tools_by_provider"].values():
        unavailable_names.update(provider["tool_names"])
    assert "send_email" in unavailable_names


def test_resolve_path_allows_extra_roots_from_env(monkeypatch, tmp_path):
    mod = _load_coder_tools_server()
    project_root = tmp_path / "project-root"
    project_root.mkdir(parents=True, exist_ok=True)
    extra_root = tmp_path / "extra-root"
    extra_root.mkdir(parents=True, exist_ok=True)
    target = extra_root / "repo"
    target.mkdir(parents=True, exist_ok=True)

    mod.PROJECT_ROOT = str(project_root)
    monkeypatch.setenv("CODER_TOOLS_ALLOWED_PATHS", str(extra_root))

    resolved = mod._resolve_path(str(target))
    assert resolved == str(target.resolve())


def test_resolve_path_denies_outside_roots_without_env(monkeypatch, tmp_path):
    mod = _load_coder_tools_server()
    project_root = tmp_path / "project-root"
    project_root.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside"
    outside.mkdir(parents=True, exist_ok=True)

    mod.PROJECT_ROOT = str(project_root)
    monkeypatch.delenv("CODER_TOOLS_ALLOWED_PATHS", raising=False)

    try:
        mod._resolve_path(str(outside))
    except ValueError as e:
        assert "outside allowed roots" in str(e)
    else:
        raise AssertionError("expected ValueError for path outside allowed roots")

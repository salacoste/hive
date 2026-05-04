"""Focused unit tests for Telegram bridge command and callback UX."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from framework.server.telegram_bridge import TelegramBridge
from framework.runtime.event_bus import EventType


class _DummyManager:
    def default_project_id(self) -> str:
        return "default"

    def list_projects(self) -> list[dict[str, str]]:
        return [{"id": "default", "name": "Default"}]

    def get_session(self, _session_id: str) -> Any | None:
        return None


def test_telegram_bridge_persists_and_restores_chat_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state_path = tmp_path / "telegram-bridge-state.json"
    monkeypatch.setenv("HIVE_TELEGRAM_STATE_PATH", str(state_path))

    bridge = TelegramBridge(_DummyManager())
    bridge._bind_chat("188207447", "session_abc")

    restored = TelegramBridge(_DummyManager())
    restored._load_persistent_state()

    assert restored._chat_session.get("188207447") == "session_abc"
    assert "188207447" in restored._session_chats.get("session_abc", set())


def test_telegram_bridge_persists_known_chats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state_path = tmp_path / "telegram-bridge-state.json"
    monkeypatch.setenv("HIVE_TELEGRAM_STATE_PATH", str(state_path))

    bridge = TelegramBridge(_DummyManager())
    bridge._remember_chat("188207447")

    restored = TelegramBridge(_DummyManager())
    restored._load_persistent_state()

    assert "188207447" in restored._known_chats


def test_telegram_bridge_persists_selected_bee(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state_path = tmp_path / "telegram-bridge-state.json"
    monkeypatch.setenv("HIVE_TELEGRAM_STATE_PATH", str(state_path))

    bridge = TelegramBridge(_DummyManager())
    bridge._set_queen_for_chat("188207447", "queen_growth")

    restored = TelegramBridge(_DummyManager())
    restored._load_persistent_state()

    assert restored._selected_queen_id("188207447") == "queen_growth"


@pytest.mark.asyncio
async def test_restart_recovers_bound_chat_by_resuming_same_session_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = tmp_path / "telegram-bridge-state.json"
    monkeypatch.setenv("HIVE_TELEGRAM_STATE_PATH", str(state_path))

    class _RecordingEventBus:
        def subscribe(self, event_types: list[EventType], handler: Any) -> str:
            return f"sub-{len(event_types)}"

    class _Session:
        def __init__(self, sid: str) -> None:
            self.id = sid
            self.event_bus = _RecordingEventBus()
            self.project_id = "default"
            self.queen_name = None

    class _Manager:
        def __init__(self) -> None:
            self._sessions: dict[str, Any] = {}
            self.create_calls: list[dict[str, Any]] = []

        def default_project_id(self) -> str:
            return "default"

        def list_projects(self) -> list[dict[str, str]]:
            return [{"id": "default", "name": "Default"}]

        def get_project(self, project_id: str) -> dict[str, str] | None:
            if project_id == "default":
                return {"id": "default", "name": "Default"}
            return None

        def list_sessions(self, project_id: str | None = None) -> list[Any]:
            return [s for s in self._sessions.values() if project_id in {None, s.project_id}]

        def get_session(self, session_id: str) -> Any | None:
            return self._sessions.get(session_id)

        async def create_session(
            self,
            project_id: str | None = None,
            queen_resume_from: str | None = None,
        ) -> Any:
            self.create_calls.append(
                {
                    "project_id": project_id,
                    "queen_resume_from": queen_resume_from,
                }
            )
            sid = str(queen_resume_from or "session-fresh")
            session = _Session(sid)
            session.project_id = project_id or "default"
            self._sessions[sid] = session
            return session

    # Process #1: bridge persists chat -> session binding.
    manager_before = _Manager()
    bridge_before = TelegramBridge(manager_before)
    bridge_before._set_queen_for_chat("42", "queen_growth")
    bridge_before._bind_chat("42", "session-restart-1")
    assert state_path.exists()

    # Process #2 (after restart): no live session in memory, binding restored
    # from state file and resumed via queen_resume_from with same session id.
    manager_after = _Manager()
    bridge_after = TelegramBridge(manager_after)
    bridge_after._load_persistent_state()
    assert bridge_after._chat_session.get("42") == "session-restart-1"

    sid, session = await bridge_after._ensure_bound_session("42")

    assert sid == "session-restart-1"
    assert bridge_after._chat_session.get("42") == "session-restart-1"
    assert bridge_after._selected_queen_id("42") == "queen_growth"
    assert getattr(session, "queen_name", None) == "queen_growth"
    assert manager_after.create_calls == [
        {"project_id": None, "queen_resume_from": "session-restart-1"},
    ]


@pytest.mark.asyncio
async def test_menu_status_shortcut_dispatches_to_status_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[str] = []

    async def _fake_send_status(chat_id: str) -> None:
        called.append(chat_id)

    monkeypatch.setattr(bridge, "_send_status", _fake_send_status)

    handled = await bridge._handle_command("42", TelegramBridge.MENU_STATUS)
    assert handled is True
    assert called == ["42"]


@pytest.mark.asyncio
async def test_web_input_auto_rebinds_chat_by_project_and_queen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = tmp_path / "telegram-bridge-state.json"
    monkeypatch.setenv("HIVE_TELEGRAM_STATE_PATH", str(state_path))

    class _Session:
        def __init__(self, sid: str, *, project_id: str, queen_name: str) -> None:
            self.id = sid
            self.project_id = project_id
            self.queen_name = queen_name

    class _Manager:
        def __init__(self) -> None:
            self._sessions: dict[str, Any] = {
                "session-old": _Session("session-old", project_id="default", queen_name="queen_growth"),
                "session-new": _Session("session-new", project_id="default", queen_name="queen_growth"),
            }

        def default_project_id(self) -> str:
            return "default"

        def list_projects(self) -> list[dict[str, str]]:
            return [{"id": "default", "name": "Default"}]

        def get_session(self, session_id: str) -> Any | None:
            return self._sessions.get(session_id)

    bridge = TelegramBridge(_Manager())
    bridge._set_queen_for_chat("42", "queen_growth")
    bridge._bind_chat("42", "session-old")

    sent: list[str] = []

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append(f"{chat_id}:{text}")

    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    event = SimpleNamespace(
        stream_id="queen",
        data={"content": "fix applied", "source": "web"},
    )
    await bridge._on_client_input_received("session-new", event)

    assert bridge._chat_session.get("42") == "session-new"
    assert any(msg.startswith("42:🌐 Web user: fix applied") for msg in sent)


@pytest.mark.asyncio
async def test_bees_command_dispatches_to_bees_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[str] = []

    async def _fake_send_bees(chat_id: str) -> None:
        called.append(chat_id)

    monkeypatch.setattr(bridge, "_send_bees", _fake_send_bees)

    handled = await bridge._handle_command("42", "/bees")
    assert handled is True
    assert called == ["42"]


@pytest.mark.asyncio
async def test_bee_command_dispatches_activation(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[tuple[str, str]] = []

    async def _fake_activate(chat_id: str, queen_id: str) -> None:
        called.append((chat_id, queen_id))

    monkeypatch.setattr(bridge, "_is_known_queen_id", lambda qid: qid == "queen_growth")
    monkeypatch.setattr(bridge, "_activate_queen_for_chat", _fake_activate)

    handled = await bridge._handle_command("42", "/bee queen_growth")
    assert handled is True
    assert called == [("42", "queen_growth")]


@pytest.mark.asyncio
async def test_bee_command_without_arg_returns_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    sent: list[str] = []

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append(text)

    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    handled = await bridge._handle_command("42", "/bee")
    assert handled is True
    assert sent == ["Usage: /bee <queen_id>"]


@pytest.mark.asyncio
async def test_send_status_includes_docker_lane_line(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    sent: list[str] = []

    class _Session:
        graph_runtime = None
        graph_id = None
        loaded_at = 0.0
        available_triggers: dict[str, Any] = {}
        active_trigger_ids: set[str] = set()
        phase_state = None

    async def _fake_ensure(chat_id: str) -> tuple[str, Any]:
        return "session-1", _Session()

    async def _fake_lane(chat_id: str, *, project_id: str) -> str:
        return "Docker lane: off (disabled); reason=feature_flag_disabled"

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append(text)

    monkeypatch.setattr(bridge, "_ensure_bound_session", _fake_ensure)
    monkeypatch.setattr(bridge, "_docker_lane_status_line", _fake_lane)
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    await bridge._send_status("42")

    assert len(sent) == 1
    assert "Session status" in sent[0]
    assert "Docker lane: off (disabled); reason=feature_flag_disabled" in sent[0]


@pytest.mark.asyncio
async def test_digest_command_dispatches_with_non_proactive_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[tuple[str, bool]] = []

    async def _fake_digest(chat_id: str, *, proactive: bool = False) -> bool:
        called.append((chat_id, proactive))
        return True

    monkeypatch.setattr(bridge, "_send_retention_digest", _fake_digest)

    handled = await bridge._handle_command("42", "/digest")
    assert handled is True
    assert called == [("42", False)]


@pytest.mark.asyncio
async def test_autodigest_command_dispatches_with_non_proactive_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[tuple[str, bool]] = []

    async def _fake_digest(chat_id: str, *, proactive: bool = False) -> bool:
        called.append((chat_id, proactive))
        return True

    monkeypatch.setattr(bridge, "_send_autonomous_digest", _fake_digest)

    handled = await bridge._handle_command("42", "/autodigest")
    assert handled is True
    assert called == [("42", False)]


@pytest.mark.asyncio
async def test_credentials_commands_dispatch_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[str] = []

    async def _fake_send(chat_id: str) -> None:
        called.append(chat_id)

    monkeypatch.setattr(bridge, "_send_credentials_readiness", _fake_send)

    handled_short = await bridge._handle_command("42", "/creds")
    handled_full = await bridge._handle_command("42", "/credentials")
    handled_menu = await bridge._handle_command("42", TelegramBridge.MENU_CREDENTIALS)
    assert handled_short is True
    assert handled_full is True
    assert handled_menu is True
    assert called == ["42", "42", "42"]


@pytest.mark.asyncio
async def test_intake_template_command_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[str] = []

    async def _fake_send(chat_id: str) -> None:
        called.append(chat_id)

    monkeypatch.setattr(bridge, "_send_intake_template", _fake_send)

    handled = await bridge._handle_command("42", "/intake_template")
    assert handled is True
    assert called == ["42"]


@pytest.mark.asyncio
async def test_toolchain_plan_command_dispatches_with_repository_arg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[tuple[str, str | None, str | None]] = []

    async def _fake_plan(
        chat_id: str,
        *,
        workspace_path: str | None = None,
        repository: str | None = None,
    ) -> None:
        called.append((chat_id, workspace_path, repository))

    monkeypatch.setattr(bridge, "_plan_project_toolchain", _fake_plan)

    handled = await bridge._handle_command("42", "/toolchain_plan https://github.com/acme/repo")
    assert handled is True
    assert called == [("42", None, "https://github.com/acme/repo")]


@pytest.mark.asyncio
async def test_toolchain_approve_command_dispatches_with_optional_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[tuple[str, str | None]] = []

    async def _fake_approve(chat_id: str, *, confirm_token: str | None = None) -> None:
        called.append((chat_id, confirm_token))

    monkeypatch.setattr(bridge, "_approve_project_toolchain", _fake_approve)

    handled_no_token = await bridge._handle_command("42", "/toolchain_approve")
    handled_with_token = await bridge._handle_command("42", "/toolchain_approve APPLY_NODE_ABC12345")
    assert handled_no_token is True
    assert handled_with_token is True
    assert called == [("42", None), ("42", "APPLY_NODE_ABC12345")]


@pytest.mark.asyncio
async def test_newrepo_command_dispatches_plan_with_parsed_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[tuple[str, str, str | None, str]] = []

    async def _fake_plan(
        chat_id: str,
        *,
        name: str,
        owner: str | None = None,
        visibility: str = "private",
    ) -> None:
        called.append((chat_id, name, owner, visibility))

    monkeypatch.setattr(bridge, "_plan_new_repository", _fake_plan)

    handled = await bridge._handle_command(
        "42",
        "/newrepo hive-demo owner=acme visibility=public",
    )
    assert handled is True
    assert called == [("42", "hive-demo", "acme", "public")]


@pytest.mark.asyncio
async def test_newrepo_confirm_callback_dispatches_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    calls: list[str] = []
    sent: list[str] = []
    api_calls: list[tuple[str, dict[str, Any]]] = []

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        api_calls.append((method, payload))
        return {"ok": True}

    async def _fake_confirm(chat_id: str) -> None:
        calls.append(chat_id)

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append(text)

    monkeypatch.setattr(bridge, "_api", _fake_api)
    monkeypatch.setattr(bridge, "_confirm_new_repository", _fake_confirm)
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    callback_data = bridge._register_callback(chat_id="42", action="confirm_newrepo", payload={})
    await bridge._handle_callback_query(
        {
            "id": "cb-newrepo-confirm",
            "from": {"is_bot": False},
            "message": {"chat": {"id": "42"}, "message_id": 303},
            "data": callback_data,
        }
    )

    assert calls == ["42"]
    assert "✅ Selected: create repository" in sent
    assert any(call[0] == "editMessageReplyMarkup" for call in api_calls)


@pytest.mark.asyncio
async def test_repo_command_dispatches_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[tuple[str, str]] = []

    async def _fake_bind(chat_id: str, *, repository: str) -> None:
        called.append((chat_id, repository))

    monkeypatch.setattr(bridge, "_bind_project_repository", _fake_bind)

    handled = await bridge._handle_command("42", "/repo https://github.com/acme/demo")
    assert handled is True
    assert called == [("42", "https://github.com/acme/demo")]


@pytest.mark.asyncio
async def test_onboard_command_dispatches_with_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[tuple[str, dict[str, Any]]] = []

    async def _fake_onboard(chat_id: str, *, payload: dict[str, Any] | None = None) -> None:
        called.append((chat_id, payload or {}))

    monkeypatch.setattr(bridge, "_run_project_onboarding", _fake_onboard)

    handled = await bridge._handle_command(
        "42",
        "/onboard stack=node template_id=fullstack-platform workspace_path=/app",
    )
    assert handled is True
    assert called == [
        (
            "42",
            {
                "stack": "node",
                "template_id": "fullstack-platform",
                "workspace_path": "/app",
            },
        )
    ]


@pytest.mark.asyncio
async def test_bootstrap_command_dispatches_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[tuple[str, dict[str, Any]]] = []

    async def _fake_plan(chat_id: str, plan: dict[str, Any]) -> None:
        called.append((chat_id, plan))

    monkeypatch.setattr(bridge, "_plan_bootstrap_flow", _fake_plan)

    handled = await bridge._handle_command(
        "42",
        "/bootstrap repo https://github.com/acme/demo --task Fix login retry race --title Login race fix --criteria tests pass|review clear --max-steps 16",
    )
    assert handled is True
    assert len(called) == 1
    chat_id, plan = called[0]
    assert chat_id == "42"
    assert plan["mode"] == "repo"
    assert plan["repository"] == "https://github.com/acme/demo"
    assert plan["task_title"] == "Login race fix"
    assert plan["task_goal"] == "Fix login retry race"
    assert plan["acceptance_criteria"] == ["tests pass", "review clear"]
    assert plan["max_steps"] == 16


@pytest.mark.asyncio
async def test_bootstrap_confirm_callback_dispatches_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    calls: list[str] = []
    sent: list[str] = []
    api_calls: list[tuple[str, dict[str, Any]]] = []

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        api_calls.append((method, payload))
        return {"ok": True}

    async def _fake_execute(chat_id: str) -> None:
        calls.append(chat_id)

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append(text)

    monkeypatch.setattr(bridge, "_api", _fake_api)
    monkeypatch.setattr(bridge, "_execute_bootstrap_flow", _fake_execute)
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    callback_data = bridge._register_callback(chat_id="42", action="confirm_bootstrap", payload={})
    await bridge._handle_callback_query(
        {
            "id": "cb-bootstrap-confirm",
            "from": {"is_bot": False},
            "message": {"chat": {"id": "42"}, "message_id": 404},
            "data": callback_data,
        }
    )

    assert calls == ["42"]
    assert "✅ Selected: run bootstrap flow" in sent
    assert any(call[0] == "editMessageReplyMarkup" for call in api_calls)


@pytest.mark.asyncio
async def test_execute_bootstrap_flow_success_reports_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    sent: list[str] = []

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append(text)

    async def _fake_core_api_json(
        *,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: int = 25,
    ) -> tuple[int, dict[str, Any]]:
        if method == "POST" and path.endswith("/repository/bind"):
            return 200, {
                "repository": {
                    "full_name": "acme/demo",
                    "html_url": "https://github.com/acme/demo",
                }
            }
        if method == "POST" and path.endswith("/onboarding"):
            return 200, {"ready": True, "workspace_path": "/app/demo", "checks": []}
        if method == "POST" and path.endswith("/autonomous/backlog"):
            return 201, {"id": "task-1"}
        if method == "POST" and path.endswith("/autonomous/execute-next"):
            return 200, {
                "run_id": "run-1",
                "terminal": True,
                "terminal_status": "completed",
                "selected_task": {"id": "task-1"},
            }
        if method == "GET" and path.endswith("/autonomous/runs/run-1/report"):
            return 200, {
                "report": {
                    "pr": {"url": "https://github.com/acme/demo/pull/5"},
                }
            }
        return 500, {"error": f"unexpected call: {method} {path}"}

    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)
    monkeypatch.setattr(bridge, "_core_api_json", _fake_core_api_json)

    bridge._pending_bootstrap["42"] = {
        "project_id": "default",
        "mode": "repo",
        "repository": "https://github.com/acme/demo",
        "task_title": "First task",
        "task_goal": "Implement first feature",
        "acceptance_criteria": ["tests pass"],
        "priority": "high",
        "max_steps": 12,
        "onboarding_payload": {},
        "expires_at": 9999999999.0,
    }

    await bridge._execute_bootstrap_flow("42")

    assert "42" not in bridge._pending_bootstrap
    assert any("Bootstrap started: trace=" in msg for msg in sent)
    assert any("Step 1/4 done" in msg for msg in sent)
    assert any("Step 2/4 done" in msg for msg in sent)
    assert any("Step 3/4 done" in msg for msg in sent)
    final_msgs = [msg for msg in sent if "Bootstrap completed: trace=" in msg]
    assert final_msgs
    final = final_msgs[-1]
    assert "project=default" in final
    assert "run_id=run-1" in final
    assert "report=/api/projects/default/autonomous/runs/run-1/report" in final
    assert "pr=https://github.com/acme/demo/pull/5" in final


@pytest.mark.asyncio
async def test_toggle_command_hides_then_restores_reply_keyboard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    sent: list[dict[str, Any]] = []

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    handled_hide = await bridge._handle_command("42", "/toggle")
    assert handled_hide is True
    assert bridge._is_menu_visible("42") is False
    assert len(sent) == 2
    assert sent[0]["reply_markup"] == {"remove_keyboard": True}

    sent.clear()
    handled_show = await bridge._handle_command("42", "/toggle")
    assert handled_show is True
    assert bridge._is_menu_visible("42") is True
    assert len(sent) == 1
    assert isinstance(sent[0]["reply_markup"], dict)
    assert "keyboard" in sent[0]["reply_markup"]


@pytest.mark.asyncio
async def test_show_digest_callback_invokes_digest_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[tuple[str, bool]] = []

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        # answerCallbackQuery is acknowledged by Telegram bridge before action dispatch.
        return {"ok": True, "method": method, "payload": payload}

    async def _fake_digest(chat_id: str, *, proactive: bool = False) -> bool:
        called.append((chat_id, proactive))
        return True

    monkeypatch.setattr(bridge, "_api", _fake_api)
    monkeypatch.setattr(bridge, "_send_retention_digest", _fake_digest)

    callback_data = bridge._register_callback(chat_id="42", action="show_digest", payload={})
    callback = {
        "id": "cb-1",
        "from": {"is_bot": False},
        "message": {"chat": {"id": "42"}},
        "data": callback_data,
    }
    await bridge._handle_callback_query(callback)

    assert called == [("42", False)]


@pytest.mark.asyncio
async def test_show_autodigest_callback_invokes_autonomous_digest_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    called: list[tuple[str, bool]] = []

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "method": method, "payload": payload}

    async def _fake_digest(chat_id: str, *, proactive: bool = False) -> bool:
        called.append((chat_id, proactive))
        return True

    monkeypatch.setattr(bridge, "_api", _fake_api)
    monkeypatch.setattr(bridge, "_send_autonomous_digest", _fake_digest)

    callback_data = bridge._register_callback(chat_id="42", action="show_autodigest", payload={})
    callback = {
        "id": "cb-2",
        "from": {"is_bot": False},
        "message": {"chat": {"id": "42"}},
        "data": callback_data,
    }
    await bridge._handle_callback_query(callback)

    assert called == [("42", False)]


@pytest.mark.asyncio
async def test_toolchain_callbacks_dispatch_plan_and_approve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    planned: list[tuple[str, str | None, str | None]] = []
    approved: list[tuple[str, str | None]] = []

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "method": method, "payload": payload}

    async def _fake_plan(
        chat_id: str,
        *,
        workspace_path: str | None = None,
        repository: str | None = None,
    ) -> None:
        planned.append((chat_id, workspace_path, repository))

    async def _fake_approve(chat_id: str, *, confirm_token: str | None = None) -> None:
        approved.append((chat_id, confirm_token))

    monkeypatch.setattr(bridge, "_api", _fake_api)
    monkeypatch.setattr(bridge, "_plan_project_toolchain", _fake_plan)
    monkeypatch.setattr(bridge, "_approve_project_toolchain", _fake_approve)

    cb_plan = bridge._register_callback(
        chat_id="42",
        action="plan_toolchain",
        payload={"repository": "https://github.com/acme/repo"},
    )
    await bridge._handle_callback_query(
        {
            "id": "cb-toolchain-plan",
            "from": {"is_bot": False},
            "message": {"chat": {"id": "42"}},
            "data": cb_plan,
        }
    )

    cb_approve = bridge._register_callback(
        chat_id="42",
        action="approve_toolchain",
        payload={"token": "APPLY_NODE_ABC12345"},
    )
    await bridge._handle_callback_query(
        {
            "id": "cb-toolchain-approve",
            "from": {"is_bot": False},
            "message": {"chat": {"id": "42"}},
            "data": cb_approve,
        }
    )

    assert planned == [("42", None, "https://github.com/acme/repo")]
    assert approved == [("42", "APPLY_NODE_ABC12345")]


@pytest.mark.asyncio
async def test_send_choice_callback_acks_and_injects_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    sent: list[str] = []
    injected: list[tuple[str, str]] = []
    api_calls: list[tuple[str, dict[str, Any]]] = []

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        api_calls.append((method, payload))
        return {"ok": True, "method": method, "payload": payload}

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append(text)

    async def _fake_inject(chat_id: str, text: str) -> None:
        injected.append((chat_id, text))

    monkeypatch.setattr(bridge, "_api", _fake_api)
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)
    monkeypatch.setattr(bridge, "_inject_user_input", _fake_inject)

    bridge._chat_session["42"] = "session-1"
    bridge._last_input_sig[("42", "session-1")] = "sig"
    bridge._pending_choice["42"] = {
        "session_id": "session-1",
        "options": ["Approve", "Discuss"],
        "prompt": "Proceed?",
        "expires_at": 9999999999.0,
    }

    callback_data = bridge._register_callback(
        chat_id="42",
        action="send_choice",
        payload={"text": "Approve"},
    )
    await bridge._handle_callback_query(
        {
            "id": "cb-choice",
            "from": {"is_bot": False},
            "message": {"chat": {"id": "42"}, "message_id": 101},
            "data": callback_data,
        }
    )

    assert sent == ["✅ Selected: Approve"]
    assert injected == [("42", "Approve")]
    assert "42" not in bridge._pending_choice
    assert ("42", "session-1") not in bridge._last_input_sig
    assert any(call[0] == "editMessageReplyMarkup" for call in api_calls)


@pytest.mark.asyncio
async def test_question_answer_callback_clears_keyboard_and_echoes_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    sent: list[str] = []
    injected: list[tuple[str, str]] = []
    api_calls: list[tuple[str, dict[str, Any]]] = []

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        api_calls.append((method, payload))
        return {"ok": True, "method": method, "payload": payload}

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append(text)

    async def _fake_inject(chat_id: str, text: str) -> None:
        injected.append((chat_id, text))

    monkeypatch.setattr(bridge, "_api", _fake_api)
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)
    monkeypatch.setattr(bridge, "_inject_user_input", _fake_inject)

    bridge._chat_session["42"] = "session-qq"
    bridge._pending_questions["42"] = {
        "session_id": "session-qq",
        "questions": [{"id": "delivery", "prompt": "Как доставлять изменения?", "options": ["Создать PR"]}],
        "index": 0,
        "answers": [],
        "expires_at": 9999999999.0,
    }

    callback_data = bridge._register_callback(
        chat_id="42",
        action="question_answer",
        payload={"answer": "Создать PR"},
    )
    await bridge._handle_callback_query(
        {
            "id": "cb-question",
            "from": {"is_bot": False},
            "message": {"chat": {"id": "42"}, "message_id": 202},
            "data": callback_data,
        }
    )

    assert any(call[0] == "editMessageReplyMarkup" for call in api_calls)
    assert "✅ Selected: Создать PR" in sent
    assert injected and injected[0][0] == "42"
    assert "Создать PR" in injected[0][1]


@pytest.mark.asyncio
async def test_inject_user_input_publishes_client_input_received_for_web_mirror() -> None:
    class _RecordingEventBus:
        def __init__(self) -> None:
            self.published: list[Any] = []

        def subscribe(self, event_types: list[EventType], handler: Any) -> str:
            return f"sub-{len(event_types)}"

        async def publish(self, event: Any) -> None:
            self.published.append(event)

    class _Session:
        def __init__(self) -> None:
            self.id = "session-1"
            self.event_bus = _RecordingEventBus()
            self.project_id = "default"
            self.queen_name = "queen_technology"
            self.graph_runtime = None
            self.queen_task = None

    class _Manager:
        def __init__(self, session: _Session) -> None:
            self._session = session

        def default_project_id(self) -> str:
            return "default"

        def list_projects(self) -> list[dict[str, str]]:
            return [{"id": "default", "name": "Default"}]

        def get_session(self, session_id: str) -> Any | None:
            if session_id == self._session.id:
                return self._session
            return None

    class _Node:
        def __init__(self) -> None:
            self.injected: list[tuple[str, bool]] = []

        async def inject_event(self, text: str, *, is_client_input: bool = False) -> None:
            self.injected.append((text, is_client_input))

    session = _Session()
    manager = _Manager(session)
    bridge = TelegramBridge(manager)
    bridge._bind_chat("42", "session-1")

    node = _Node()

    async def _fake_await_queen_node(*args: Any, **kwargs: Any) -> Any:
        return node

    bridge._await_queen_node = _fake_await_queen_node  # type: ignore[method-assign]

    await bridge._inject_user_input("42", "ping from telegram")

    assert node.injected == [("ping from telegram", True)]
    assert len(session.event_bus.published) == 1
    evt = session.event_bus.published[0]
    assert evt.type == EventType.CLIENT_INPUT_RECEIVED
    assert evt.data.get("content") == "ping from telegram"
    assert evt.data.get("source") == "telegram"
    assert evt.data.get("chat_id") == "42"


@pytest.mark.asyncio
async def test_send_choice_callback_handles_no_worker_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _RecordingEventBus:
        def subscribe(self, event_types: list[EventType], handler: Any) -> str:
            return f"sub-{len(event_types)}"

        async def publish(self, event: Any) -> None:
            return None

    class _Session:
        def __init__(self) -> None:
            self.id = "session-noworker"
            self.event_bus = _RecordingEventBus()
            self.project_id = "default"
            self.queen_name = "queen_technology"
            self.graph_runtime = None
            self.queen_task = None

    class _Manager:
        def __init__(self, session: _Session) -> None:
            self._session = session
            self.revive_calls = 0

        def default_project_id(self) -> str:
            return "default"

        def list_projects(self) -> list[dict[str, str]]:
            return [{"id": "default", "name": "Default"}]

        def get_project(self, project_id: str) -> dict[str, str] | None:
            if project_id == "default":
                return {"id": "default", "name": "Default"}
            return None

        def get_session(self, session_id: str) -> Any | None:
            if session_id == self._session.id:
                return self._session
            return None

        async def revive_queen(self, session: Any) -> None:
            self.revive_calls += 1

    session = _Session()
    manager = _Manager(session)
    bridge = TelegramBridge(manager)
    sent: list[str] = []
    api_calls: list[tuple[str, dict[str, Any]]] = []

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        api_calls.append((method, payload))
        return {"ok": True, "method": method, "payload": payload}

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append(text)

    async def _fake_await_queen_node(*args: Any, **kwargs: Any) -> Any:
        return None

    monkeypatch.setattr(bridge, "_api", _fake_api)
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)
    bridge._await_queen_node = _fake_await_queen_node  # type: ignore[method-assign]

    bridge._bind_chat("42", "session-noworker")
    bridge._pending_choice["42"] = {
        "session_id": "session-noworker",
        "options": ["Approve"],
        "prompt": "Proceed?",
        "expires_at": 9999999999.0,
    }

    callback_data = bridge._register_callback(
        chat_id="42",
        action="send_choice",
        payload={"text": "Approve"},
    )
    await bridge._handle_callback_query(
        {
            "id": "cb-choice-no-worker",
            "from": {"is_bot": False},
            "message": {"chat": {"id": "42"}, "message_id": 606},
            "data": callback_data,
        }
    )

    assert "✅ Selected: Approve" in sent
    assert "Queen is not ready yet. Try again in a moment." in sent
    assert manager.revive_calls == 1
    assert "42" not in bridge._pending_choice
    assert any(call[0] == "editMessageReplyMarkup" for call in api_calls)


def test_inline_markup_single_use_group_invalidates_sibling_callbacks() -> None:
    bridge = TelegramBridge(_DummyManager())
    markup = bridge._make_inline_markup(
        chat_id="42",
        rows=[[("Approve", "send_choice", {"text": "Approve"}), ("Discuss", "send_choice", {"text": "Discuss"})]],
    )
    row = markup["inline_keyboard"][0]
    first_data = row[0]["callback_data"]
    second_data = row[1]["callback_data"]

    first = bridge._consume_callback("42", first_data)
    second = bridge._consume_callback("42", second_data)

    assert first is not None
    action, payload = first
    assert action == "send_choice"
    assert payload["text"] == "Approve"
    assert second is None


@pytest.mark.asyncio
async def test_duplicate_callback_id_is_ignored_without_double_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    sent: list[str] = []
    injected: list[tuple[str, str]] = []
    api_calls: list[tuple[str, dict[str, Any]]] = []

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        api_calls.append((method, payload))
        return {"ok": True, "method": method, "payload": payload}

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append(text)

    async def _fake_inject(chat_id: str, text: str) -> None:
        injected.append((chat_id, text))

    monkeypatch.setattr(bridge, "_api", _fake_api)
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)
    monkeypatch.setattr(bridge, "_inject_user_input", _fake_inject)

    bridge._pending_choice["42"] = {
        "session_id": "s1",
        "options": ["Approve"],
        "prompt": "Proceed?",
        "expires_at": 9999999999.0,
    }
    callback_data = bridge._register_callback(chat_id="42", action="send_choice", payload={"text": "Approve"})
    callback = {
        "id": "cb-dup-1",
        "from": {"is_bot": False},
        "message": {"chat": {"id": "42"}, "message_id": 404},
        "data": callback_data,
    }
    await bridge._handle_callback_query(callback)
    await bridge._handle_callback_query(callback)

    assert injected == [("42", "Approve")]
    assert sent == ["✅ Selected: Approve"]
    duplicate_answers = [
        payload
        for method, payload in api_calls
        if method == "answerCallbackQuery" and str(payload.get("text") or "").strip() == "Already handled."
    ]
    assert duplicate_answers


@pytest.mark.asyncio
async def test_stale_callback_does_not_send_chat_spam(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    sent: list[str] = []
    api_calls: list[tuple[str, dict[str, Any]]] = []

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        api_calls.append((method, payload))
        return {"ok": True, "method": method, "payload": payload}

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append(text)

    monkeypatch.setattr(bridge, "_api", _fake_api)
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    await bridge._handle_callback_query(
        {
            "id": "cb-stale-1",
            "from": {"is_bot": False},
            "message": {"chat": {"id": "42"}, "message_id": 505},
            "data": "hcb:missing-token",
        }
    )

    assert sent == []
    stale_answers = [
        payload
        for method, payload in api_calls
        if method == "answerCallbackQuery"
        and str(payload.get("text") or "").strip() == "This option is no longer active."
    ]
    assert stale_answers


@pytest.mark.asyncio
async def test_autodigest_proactive_skips_when_no_risky_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())

    class _Resp:
        status = 200

        async def text(self) -> str:
            return (
                '{"status":"ok","summary":{"projects_total":1,"ok":1,"failed":0,'
                '"outcomes":{"idle":1}},"projects":[{"project_id":"default","outcome":"idle"}]}'
            )

    class _Ctx:
        async def __aenter__(self) -> _Resp:
            return _Resp()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class _Client:
        def post(self, url: str, json: dict[str, Any], timeout: int) -> _Ctx:
            return _Ctx()

    sent: list[str] = []

    async def _fake_send_text(chat_id: str, text: str, *, reply_markup=None) -> None:
        sent.append(text)

    bridge._client = _Client()  # type: ignore[assignment]
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    ok = await bridge._send_autonomous_digest("42", proactive=True)
    assert ok is False
    assert sent == []


@pytest.mark.asyncio
async def test_autodigest_includes_release_matrix_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate_path = tmp_path / "gate-latest.json"
    gate_path.write_text(
        (
            "{"
            '"generated_at":"2026-04-23T14:00:00",'
            '"release_matrix":{"status":"fail","must_passed":5,"must_total":6}'
            "}"
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HIVE_ACCEPTANCE_GATE_SHARED_JSON_PATH", str(gate_path))
    bridge = TelegramBridge(_DummyManager())

    class _Resp:
        status = 200

        async def text(self) -> str:
            return (
                '{"status":"ok","summary":{"projects_total":1,"ok":1,"failed":0,'
                '"outcomes":{"completed":1}},'
                '"projects":[{"project_id":"app-a","outcome":"completed","terminal_status":"completed","pr_ready":true}],'
                '"highlights":{"terminal_ready_projects":["app-a"],"blocked_projects":[],"manual_deferred_projects":[]}}'
            )

    class _Ctx:
        async def __aenter__(self) -> _Resp:
            return _Resp()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class _Client:
        def post(self, url: str, json: dict[str, Any], timeout: int) -> _Ctx:
            return _Ctx()

    sent: list[str] = []

    async def _fake_send_text(chat_id: str, text: str, *, reply_markup=None) -> None:
        sent.append(text)

    bridge._client = _Client()  # type: ignore[assignment]
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    ok = await bridge._send_autonomous_digest("42", proactive=False)
    assert ok is True
    assert len(sent) == 1
    body = sent[0]
    assert "release_matrix: fail (must 5/6)" in body
    assert "release_matrix_at: 2026-04-23T14:00:00" in body


@pytest.mark.asyncio
async def test_autodigest_proactive_sends_when_matrix_is_risky(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate_path = tmp_path / "gate-latest.json"
    gate_path.write_text(
        (
            "{"
            '"generated_at":"2026-04-23T14:00:00",'
            '"release_matrix":{"status":"fail","must_passed":5,"must_total":6}'
            "}"
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HIVE_ACCEPTANCE_GATE_SHARED_JSON_PATH", str(gate_path))
    bridge = TelegramBridge(_DummyManager())

    class _Resp:
        status = 200

        async def text(self) -> str:
            return (
                '{"status":"ok","summary":{"projects_total":1,"ok":1,"failed":0,'
                '"outcomes":{"idle":1}},"projects":[{"project_id":"default","outcome":"idle"}]}'
            )

    class _Ctx:
        async def __aenter__(self) -> _Resp:
            return _Resp()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class _Client:
        def post(self, url: str, json: dict[str, Any], timeout: int) -> _Ctx:
            return _Ctx()

    sent: list[str] = []

    async def _fake_send_text(chat_id: str, text: str, *, reply_markup=None) -> None:
        sent.append(text)

    bridge._client = _Client()  # type: ignore[assignment]
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    ok = await bridge._send_autonomous_digest("42", proactive=True)
    assert ok is True
    assert len(sent) == 1
    assert "release_matrix: fail (must 5/6)" in sent[0]


@pytest.mark.asyncio
async def test_autodigest_action_oriented_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())

    class _Resp:
        status = 200

        async def text(self) -> str:
            return (
                '{"status":"ok","summary":{"projects_total":2,"ok":2,"failed":0,'
                '"outcomes":{"completed":1,"manual_deferred":1}},'
                '"projects":['
                '{"project_id":"app-a","outcome":"completed","terminal_status":"completed","pr_ready":true},'
                '{"project_id":"app-b","outcome":"manual_deferred","terminal_status":null,"pr_ready":false}'
                '],'
                '"highlights":{'
                '"terminal_ready_projects":["app-a"],'
                '"blocked_projects":[],'
                '"manual_deferred_projects":["app-b"],'
                '"top_risks":[]'
                '}}'
            )

    class _Ctx:
        async def __aenter__(self) -> _Resp:
            return _Resp()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class _Client:
        def post(self, url: str, json: dict[str, Any], timeout: int) -> _Ctx:
            return _Ctx()

    sent: list[str] = []

    async def _fake_send_text(chat_id: str, text: str, *, reply_markup=None) -> None:
        sent.append(text)

    bridge._client = _Client()  # type: ignore[assignment]
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    ok = await bridge._send_autonomous_digest("42", proactive=False)
    assert ok is True
    assert len(sent) == 1
    body = sent[0]
    assert "ready_for_pr: app-a" in body
    assert "manual_deferred: app-b" in body
    assert "Next actions:" in body


@pytest.mark.asyncio
async def test_autodigest_includes_telegram_conflict_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = TelegramBridge(_DummyManager())
    bridge._poll_conflict_409_count = 5
    bridge._last_poll_conflict_409_at = 1_700_000_100.0
    bridge._last_poll_conflict_recover_result = "delete_webhook_ok"
    now = {"ts": 1_700_000_120.0}
    monkeypatch.setattr("framework.server.telegram_bridge.time.time", lambda: now["ts"])

    class _Resp:
        status = 200

        async def text(self) -> str:
            return (
                '{"status":"ok","summary":{"projects_total":1,"ok":1,"failed":0,'
                '"outcomes":{"idle":1}},"projects":[{"project_id":"default","outcome":"idle"}]}'
            )

    class _Ctx:
        async def __aenter__(self) -> _Resp:
            return _Resp()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class _Client:
        def post(self, url: str, json: dict[str, Any], timeout: int) -> _Ctx:
            return _Ctx()

    sent: list[str] = []

    async def _fake_send_text(chat_id: str, text: str, *, reply_markup=None) -> None:
        sent.append(text)

    bridge._client = _Client()  # type: ignore[assignment]
    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    ok = await bridge._send_autonomous_digest("42", proactive=False)
    assert ok is True
    assert len(sent) == 1
    body = sent[0]
    assert "telegram_conflicts_409: count=5" in body
    assert "warning=telegram 409 conflicts rising" in body


def test_single_consumer_poll_lock_prevents_second_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    lock_path = tmp_path / "telegram-poll.lock"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("HIVE_TELEGRAM_POLL_LOCK_PATH", str(lock_path))
    monkeypatch.setenv("HIVE_TELEGRAM_SINGLE_CONSUMER", "1")

    bridge_a = TelegramBridge(_DummyManager())
    bridge_b = TelegramBridge(_DummyManager())

    try:
        assert bridge_a._try_acquire_poll_lock() is True
        assert bridge_a.status()["poller_owner"] is True
        assert bridge_b._try_acquire_poll_lock() is False
        assert bridge_b.status()["poller_owner"] is False
    finally:
        bridge_a._release_poll_lock()
        bridge_b._release_poll_lock()


def test_format_exception_details_includes_type_for_empty_message() -> None:
    bridge = TelegramBridge(_DummyManager())
    detail = bridge._format_exception_details(asyncio.TimeoutError())
    assert detail == "TimeoutError"


def test_format_exception_details_includes_type_and_message() -> None:
    bridge = TelegramBridge(_DummyManager())
    detail = bridge._format_exception_details(RuntimeError("poll failed"))
    assert detail == "RuntimeError: poll failed"


def test_status_includes_poll_conflict_telemetry_fields() -> None:
    bridge = TelegramBridge(_DummyManager())
    status = bridge.status()
    assert status["poll_conflict_409_count"] == 0
    assert status["last_poll_conflict_409_at"] is None
    assert status["last_poll_conflict_recover_at"] is None
    assert status["last_poll_conflict_recover_result"] is None
    assert isinstance(status["auto_clear_webhook_on_409"], bool)
    assert isinstance(status["conflict_recover_cooldown_seconds"], int)
    assert isinstance(status["conflict_warn_threshold"], int)
    assert isinstance(status["conflict_warn_window_seconds"], int)
    assert status["poll_conflict_warning_active"] is False
    assert status["last_poll_conflict_age_seconds"] is None


@pytest.mark.asyncio
async def test_poll_conflict_recovery_delete_webhook_with_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    bridge = TelegramBridge(_DummyManager())
    calls: list[tuple[str, dict[str, Any]]] = []
    now = {"ts": 1_700_000_000.0}

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append((method, payload))
        return {"ok": True}

    monkeypatch.setattr(bridge, "_api", _fake_api)
    monkeypatch.setattr("framework.server.telegram_bridge.time.time", lambda: now["ts"])

    detail = "RuntimeError: Telegram API getUpdates failed: {'ok': False, 'error_code': 409}"
    await bridge._maybe_recover_poll_conflict(detail)
    assert bridge._poll_conflict_409_count == 1
    assert bridge._last_poll_conflict_recover_result == "delete_webhook_ok"
    assert calls == [("deleteWebhook", {"drop_pending_updates": False})]

    await bridge._maybe_recover_poll_conflict(detail)
    assert bridge._poll_conflict_409_count == 2
    assert bridge._last_poll_conflict_recover_result == "cooldown"
    assert len(calls) == 1

    now["ts"] += float(bridge._poll_conflict_recover_cooldown_seconds + 1)
    await bridge._maybe_recover_poll_conflict(detail)
    assert bridge._poll_conflict_409_count == 3
    assert bridge._last_poll_conflict_recover_result == "delete_webhook_ok"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_poll_conflict_recovery_respects_disable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("HIVE_TELEGRAM_AUTO_CLEAR_WEBHOOK_ON_409", "0")
    bridge = TelegramBridge(_DummyManager())

    async def _fake_api(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("deleteWebhook should not be called when recovery is disabled")

    monkeypatch.setattr(bridge, "_api", _fake_api)
    detail = "RuntimeError: Telegram API getUpdates failed: {'ok': False, 'error_code': 409}"
    await bridge._maybe_recover_poll_conflict(detail)
    assert bridge._poll_conflict_409_count == 1
    assert bridge._last_poll_conflict_recover_result == "disabled_by_env"


@pytest.mark.asyncio
async def test_operator_recover_resets_telemetry_without_client() -> None:
    bridge = TelegramBridge(_DummyManager())
    bridge._poll_conflict_409_count = 5
    bridge._last_poll_conflict_409_at = 1700000000.0
    bridge._last_poll_conflict_recover_at = 1700000001.0
    bridge._last_poll_conflict_recover_result = "delete_webhook_ok"
    bridge._last_poll_error = "RuntimeError: Telegram API getUpdates failed: {'error_code': 409}"

    report = await bridge.operator_recover(
        force_delete_webhook=False,
        reset_conflict_telemetry=True,
        clear_last_error=True,
    )
    assert report["ok"] is True
    assert "reset_conflict_telemetry" in report["actions"]
    assert bridge._poll_conflict_409_count == 0
    assert bridge._last_poll_conflict_409_at is None
    assert bridge._last_poll_conflict_recover_at is None
    assert bridge._last_poll_conflict_recover_result is None
    assert bridge._last_poll_error is None


@pytest.mark.asyncio
async def test_operator_recover_reports_error_when_delete_webhook_requested_without_client() -> None:
    bridge = TelegramBridge(_DummyManager())
    report = await bridge.operator_recover(
        force_delete_webhook=True,
        reset_conflict_telemetry=False,
        clear_last_error=False,
    )
    assert report["ok"] is False
    assert report["error"] == "bridge_client_not_initialized"


@pytest.mark.asyncio
async def test_client_input_received_mirrors_web_message_to_bound_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    sent: list[tuple[str, str]] = []

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append((chat_id, text))

    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)
    bridge._session_chats["session-a"].add("42")

    event = SimpleNamespace(
        stream_id="queen",
        data={"content": "Deploy this repo", "source": "web"},
    )
    await bridge._on_client_input_received("session-a", event)

    assert sent == [("42", "🌐 Web user: Deploy this repo")]


@pytest.mark.asyncio
async def test_client_input_received_skips_origin_telegram_chat_but_mirrors_to_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = TelegramBridge(_DummyManager())
    sent: list[tuple[str, str]] = []

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append((chat_id, text))

    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)
    bridge._session_chats["session-a"].update({"100", "200"})

    event = SimpleNamespace(
        stream_id="queen",
        data={"content": "ping bridge", "source": "telegram", "chat_id": "100"},
    )
    await bridge._on_client_input_received("session-a", event)

    assert sent == [("200", "💬 Telegram user: ping bridge")]


@pytest.mark.asyncio
async def test_client_input_received_auto_binds_fallback_test_chat(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("HIVE_TELEGRAM_TEST_CHAT_ID", "188207447")
    monkeypatch.setenv("HIVE_TELEGRAM_STATE_PATH", str(tmp_path / "telegram-bridge-state.json"))

    bridge = TelegramBridge(_DummyManager())
    sent: list[tuple[str, str]] = []

    async def _fake_send_text(
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        sent.append((chat_id, text))

    monkeypatch.setattr(bridge, "_send_text", _fake_send_text)

    event = SimpleNamespace(
        stream_id="queen",
        data={"content": "Deploy this repo", "source": "web"},
    )
    await bridge._on_client_input_received("session-x", event)

    assert bridge._chat_session.get("188207447") == "session-x"
    assert sent == [("188207447", "🌐 Web user: Deploy this repo")]


@pytest.mark.asyncio
async def test_ensure_bound_session_subscribes_immediately_for_mirroring() -> None:
    class _RecordingEventBus:
        def __init__(self) -> None:
            self.calls: list[tuple[EventType, ...]] = []

        def subscribe(self, event_types: list[EventType], handler: Any) -> str:
            self.calls.append(tuple(event_types))
            return f"sub-{len(self.calls)}"

    class _Session:
        def __init__(self) -> None:
            self.id = "session-a"
            self.event_bus = _RecordingEventBus()

    class _Manager:
        def __init__(self, session: _Session) -> None:
            self._session = session

        def default_project_id(self) -> str:
            return "default"

        def list_projects(self) -> list[dict[str, str]]:
            return [{"id": "default", "name": "Default"}]

        def get_session(self, session_id: str) -> Any | None:
            if session_id == self._session.id:
                return self._session
            return None

    session = _Session()
    bridge = TelegramBridge(_Manager(session))
    bridge._bind_chat("42", "session-a")

    sid, _ = await bridge._ensure_bound_session("42")

    assert sid == "session-a"
    assert "session-a" in bridge._subs
    assert len(bridge._subs["session-a"]) == 4
    assert session.event_bus.calls == [
        (EventType.CLIENT_OUTPUT_DELTA,),
        (EventType.LLM_TURN_COMPLETE,),
        (EventType.CLIENT_INPUT_REQUESTED,),
        (EventType.CLIENT_INPUT_RECEIVED,),
    ]


@pytest.mark.asyncio
async def test_ensure_bound_session_creates_new_session_with_selected_bee_for_first_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _RecordingEventBus:
        def subscribe(self, event_types: list[EventType], handler: Any) -> str:
            return f"sub-{len(event_types)}"

    class _Session:
        def __init__(self, sid: str) -> None:
            self.id = sid
            self.event_bus = _RecordingEventBus()
            self.project_id = "default"
            self.queen_name = None

    class _Manager:
        def __init__(self) -> None:
            self._sessions: dict[str, Any] = {}

        def default_project_id(self) -> str:
            return "default"

        def list_projects(self) -> list[dict[str, str]]:
            return [{"id": "default", "name": "Default"}]

        def get_project(self, project_id: str) -> dict[str, str] | None:
            if project_id == "default":
                return {"id": "default", "name": "Default"}
            return None

        def list_sessions(self, project_id: str | None = None) -> list[Any]:
            return []

        async def create_session(self, project_id: str | None = None) -> Any:
            sid = "session-new"
            session = _Session(sid)
            session.project_id = project_id or "default"
            self._sessions[sid] = session
            return session

        def get_session(self, session_id: str) -> Any | None:
            return self._sessions.get(session_id)

    manager = _Manager()
    bridge = TelegramBridge(manager)

    async def _fake_choose(chat_id: str, *, first_user_message: str | None = None) -> str:
        return "queen_growth"

    monkeypatch.setattr(bridge, "_choose_queen_for_new_binding", _fake_choose)

    sid, session = await bridge._ensure_bound_session("42", first_user_message="need growth plan")

    assert sid == "session-new"
    assert getattr(session, "queen_name", None) == "queen_growth"
    assert bridge._chat_session.get("42") == "session-new"
    assert bridge._selected_queen_id("42") == "queen_growth"


@pytest.mark.asyncio
async def test_ensure_bound_session_resumes_stale_binding_before_creating_new() -> None:
    class _RecordingEventBus:
        def subscribe(self, event_types: list[EventType], handler: Any) -> str:
            return f"sub-{len(event_types)}"

    class _Session:
        def __init__(self, sid: str) -> None:
            self.id = sid
            self.event_bus = _RecordingEventBus()
            self.project_id = "default"
            self.queen_name = None

    class _Manager:
        def __init__(self) -> None:
            self._sessions: dict[str, Any] = {}
            self.create_calls: list[dict[str, Any]] = []

        def default_project_id(self) -> str:
            return "default"

        def list_projects(self) -> list[dict[str, str]]:
            return [{"id": "default", "name": "Default"}]

        def get_project(self, project_id: str) -> dict[str, str] | None:
            if project_id == "default":
                return {"id": "default", "name": "Default"}
            return None

        def list_sessions(self, project_id: str | None = None) -> list[Any]:
            return [s for s in self._sessions.values() if project_id in {None, s.project_id}]

        def get_session(self, session_id: str) -> Any | None:
            return self._sessions.get(session_id)

        async def create_session(
            self,
            project_id: str | None = None,
            queen_resume_from: str | None = None,
        ) -> Any:
            self.create_calls.append(
                {
                    "project_id": project_id,
                    "queen_resume_from": queen_resume_from,
                }
            )
            sid = str(queen_resume_from or "session-new")
            session = _Session(sid)
            session.project_id = project_id or "default"
            self._sessions[sid] = session
            return session

    manager = _Manager()
    bridge = TelegramBridge(manager)
    bridge._set_queen_for_chat("42", "queen_growth")
    bridge._bind_chat("42", "session-stale")

    sid, session = await bridge._ensure_bound_session("42")

    assert sid == "session-stale"
    assert getattr(session, "queen_name", None) == "queen_growth"
    assert bridge._chat_session.get("42") == "session-stale"
    assert manager.create_calls == [
        {"project_id": None, "queen_resume_from": "session-stale"},
    ]


@pytest.mark.asyncio
async def test_ensure_bound_session_falls_back_to_new_when_resume_fails() -> None:
    class _RecordingEventBus:
        def subscribe(self, event_types: list[EventType], handler: Any) -> str:
            return f"sub-{len(event_types)}"

    class _Session:
        def __init__(self, sid: str) -> None:
            self.id = sid
            self.event_bus = _RecordingEventBus()
            self.project_id = "default"
            self.queen_name = None

    class _Manager:
        def __init__(self) -> None:
            self._sessions: dict[str, Any] = {}
            self.create_calls: list[dict[str, Any]] = []

        def default_project_id(self) -> str:
            return "default"

        def list_projects(self) -> list[dict[str, str]]:
            return [{"id": "default", "name": "Default"}]

        def get_project(self, project_id: str) -> dict[str, str] | None:
            if project_id == "default":
                return {"id": "default", "name": "Default"}
            return None

        def list_sessions(self, project_id: str | None = None) -> list[Any]:
            return [s for s in self._sessions.values() if project_id in {None, s.project_id}]

        def get_session(self, session_id: str) -> Any | None:
            return self._sessions.get(session_id)

        async def create_session(
            self,
            project_id: str | None = None,
            queen_resume_from: str | None = None,
        ) -> Any:
            self.create_calls.append(
                {
                    "project_id": project_id,
                    "queen_resume_from": queen_resume_from,
                }
            )
            if queen_resume_from:
                raise RuntimeError("resume failed")
            session = _Session("session-fresh")
            session.project_id = project_id or "default"
            self._sessions[session.id] = session
            return session

    manager = _Manager()
    bridge = TelegramBridge(manager)
    bridge._bind_chat("42", "session-stale")

    sid, _ = await bridge._ensure_bound_session("42")

    assert sid == "session-fresh"
    assert bridge._chat_session.get("42") == "session-fresh"
    assert manager.create_calls == [
        {"project_id": None, "queen_resume_from": "session-stale"},
        {"project_id": "default", "queen_resume_from": None},
    ]

"""Focused unit tests for Telegram bridge command and callback UX."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from framework.server.telegram_bridge import TelegramBridge


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

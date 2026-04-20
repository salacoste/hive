"""Telegram <-> Hive bridge with interactive bot UI.

Features:
- long-poll Telegram Bot API updates,
- route chat text into bound Hive queen sessions,
- forward queen output snapshots back to Telegram,
- expose a keyboard-first bot UX (status/sessions/run/stop/cancel/help),
- render ask_user/ask_user_multiple choices as inline Telegram buttons.
"""

from __future__ import annotations

import asyncio
import errno
import fcntl
import json
import logging
import os
import re
import time
import uuid
from collections import defaultdict
from typing import Any
from urllib.parse import quote

from aiohttp import ClientSession

from framework.runtime.event_bus import AgentEvent, EventType
from framework.server.project_retention import build_retention_plan, resolve_retention_policy

logger = logging.getLogger(__name__)


class TelegramBridge:
    """Bidirectional Telegram bridge for Hive sessions."""

    MENU_STATUS = "Status"
    MENU_SESSIONS = "Sessions"
    MENU_NEW = "New"
    MENU_RUN = "Run"
    MENU_STOP = "Stop"
    MENU_CANCEL_TURN = "Cancel"
    MENU_HELP = "Help"
    MENU_TOGGLE = "Menu"
    MENU_PROJECTS = "Projects"
    MENU_TOOLCHAIN = "Toolchain"
    MENU_CREDENTIALS = "Credentials"

    def __init__(self, session_manager: Any) -> None:
        self._manager = session_manager
        self._token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self._enabled = bool(self._token) and (
            os.environ.get("HIVE_TELEGRAM_BRIDGE_ENABLED", "1").strip().lower()
            not in {"0", "false", "no", "off"}
        )
        self._mode = os.environ.get("HIVE_TELEGRAM_MODE", "polling").strip().lower() or "polling"
        self._single_consumer = (
            os.environ.get("HIVE_TELEGRAM_SINGLE_CONSUMER", "1").strip().lower()
            not in {"0", "false", "no", "off"}
        )
        self._poll_lock_path = os.path.expanduser(
            os.environ.get(
                "HIVE_TELEGRAM_POLL_LOCK_PATH",
                "~/.hive/server/telegram-poll.lock",
            ).strip()
            or "~/.hive/server/telegram-poll.lock"
        )
        self._state_path = os.path.expanduser(
            os.environ.get(
                "HIVE_TELEGRAM_STATE_PATH",
                "~/.hive/server/telegram-bridge-state.json",
            ).strip()
            or "~/.hive/server/telegram-bridge-state.json"
        )
        self._poll_lock_file: Any | None = None
        self._poller_owner = False
        self._startup_status = "idle"
        self._last_poll_error: str | None = None

        self._offset = 0
        self._poll_task: asyncio.Task | None = None
        self._sync_task: asyncio.Task | None = None
        self._retention_task: asyncio.Task | None = None
        self._autonomous_task: asyncio.Task | None = None
        self._client: ClientSession | None = None
        self._stopped = asyncio.Event()
        self._commands_initialized = False
        self._retention_digest_enabled = (
            os.environ.get("HIVE_TELEGRAM_RETENTION_DIGEST_ENABLED", "1").strip().lower()
            not in {"0", "false", "no", "off"}
        )
        try:
            self._retention_digest_hour = int(
                os.environ.get("HIVE_TELEGRAM_RETENTION_DIGEST_HOUR", "10").strip() or "10"
            )
        except ValueError:
            self._retention_digest_hour = 10
        self._retention_digest_hour = max(0, min(23, self._retention_digest_hour))
        self._retention_digest_minute = 0
        self._retention_last_sent_key: dict[str, str] = {}
        self._autonomous_digest_enabled = (
            os.environ.get("HIVE_TELEGRAM_AUTONOMOUS_DIGEST_ENABLED", "1").strip().lower()
            not in {"0", "false", "no", "off"}
        )
        try:
            self._autonomous_digest_hour = int(
                os.environ.get("HIVE_TELEGRAM_AUTONOMOUS_DIGEST_HOUR", "12").strip() or "12"
            )
        except ValueError:
            self._autonomous_digest_hour = 12
        self._autonomous_digest_hour = max(0, min(23, self._autonomous_digest_hour))
        self._autonomous_digest_minute = 0
        self._autonomous_last_sent_key: dict[str, str] = {}

        # chat_id -> session_id
        self._chat_session: dict[str, str] = {}
        # chat_id -> project_id
        self._chat_project: dict[str, str] = {}
        # session_id -> set(chat_id)
        self._session_chats: dict[str, set[str]] = defaultdict(set)

        # session_id -> subscription ids
        self._subs: dict[str, list[str]] = {}

        # Latest queen snapshot per session
        self._latest_snapshot: dict[str, str] = {}
        # Last snapshot delivered to each chat per session
        self._last_sent: dict[tuple[str, str], str] = {}
        # Last input-request signature sent to each chat/session
        self._last_input_sig: dict[tuple[str, str], str] = {}

        # callback token -> payload
        self._callback_payloads: dict[str, dict[str, Any]] = {}
        # callback group id -> callback token set (single-use inline decision groups)
        self._callback_groups: dict[str, set[str]] = {}
        # callback_query_id -> expires_at (duplicate callback delivery guard)
        self._seen_callback_ids: dict[str, float] = {}

        # chat_id -> pending ask_user options
        self._pending_choice: dict[str, dict[str, Any]] = {}
        # chat_id -> pending ask_user_multiple questionnaire state
        self._pending_questions: dict[str, dict[str, Any]] = {}
        # chat_id -> pending "create project from next text message"
        self._pending_new_project: dict[str, dict[str, Any]] = {}
        # chat_id -> pending "provision repository" plan waiting for confirm callback
        self._pending_new_repo: dict[str, dict[str, Any]] = {}
        # chat_id -> pending autonomous bootstrap plan waiting for confirm callback
        self._pending_bootstrap: dict[str, dict[str, Any]] = {}
        # chat_id -> whether reply keyboard is shown
        self._menu_visible: dict[str, bool] = {}
        # known chats for proactive reminders
        self._known_chats: set[str] = set()

    def _default_project_id(self) -> str:
        return self._manager.default_project_id()

    def _selected_project_id(self, chat_id: str) -> str:
        return self._chat_project.get(chat_id, self._default_project_id())

    def _set_project_for_chat(self, chat_id: str, project_id: str) -> None:
        self._chat_project[chat_id] = project_id
        self._persist_state()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @staticmethod
    def _format_exception_details(exc: BaseException) -> str:
        """Return stable exception details for logs/status, even when str(exc) is empty."""
        exc_type = type(exc).__name__
        message = str(exc).strip()
        if not message:
            return exc_type
        return f"{exc_type}: {message}"

    async def start(self) -> None:
        """Start polling and session subscription synchronization."""
        if not self._enabled:
            logger.info("Telegram bridge disabled (missing token or disabled by env)")
            self._startup_status = "disabled"
            return
        if self._client is not None:
            return
        if self._mode != "polling":
            logger.warning("Telegram bridge mode '%s' is not implemented, bridge disabled", self._mode)
            self._startup_status = f"unsupported_mode:{self._mode}"
            return
        if self._single_consumer and not self._try_acquire_poll_lock():
            self._startup_status = "poll_lock_conflict"
            return

        self._load_persistent_state()
        self._client = ClientSession()
        self._stopped.clear()
        await self._ensure_bot_commands()
        self._poll_task = asyncio.create_task(self._poll_loop(), name="telegram-bridge-poll")
        self._sync_task = asyncio.create_task(self._sync_loop(), name="telegram-bridge-sync")
        if self._retention_digest_enabled:
            self._retention_task = asyncio.create_task(
                self._retention_digest_loop(), name="telegram-bridge-retention-digest"
            )
        if self._autonomous_digest_enabled:
            self._autonomous_task = asyncio.create_task(
                self._autonomous_digest_loop(), name="telegram-bridge-autonomous-digest"
            )
        self._startup_status = "running"
        logger.info("Telegram bridge started")

    async def stop(self) -> None:
        """Stop background tasks and clean subscriptions."""
        self._stopped.set()

        for task in (self._poll_task, self._sync_task, self._retention_task, self._autonomous_task):
            if task is not None:
                task.cancel()
        for task in (self._poll_task, self._sync_task, self._retention_task, self._autonomous_task):
            if task is not None:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception("Telegram bridge task failed during shutdown")

        await self._unsubscribe_all()

        if self._client is not None:
            await self._client.close()
            self._client = None

        self._release_poll_lock()
        self._startup_status = "stopped"
        logger.info("Telegram bridge stopped")

    async def _api(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("Telegram bridge client not initialized")

        url = f"https://api.telegram.org/bot{self._token}/{method}"
        async with self._client.post(url, json=payload, timeout=35) as resp:
            data = await resp.json(content_type=None)
            if not data.get("ok"):
                raise RuntimeError(f"Telegram API {method} failed: {data}")
            return data

    async def _ensure_bot_commands(self) -> None:
        """Register command hints shown by Telegram when user types '/'."""
        if self._commands_initialized:
            return
        commands = [
            {"command": "start", "description": "Open control center"},
            {"command": "menu", "description": "Show main button menu"},
            {"command": "show", "description": "Show button menu"},
            {"command": "hide", "description": "Hide button menu"},
            {"command": "status", "description": "Current session status"},
            {"command": "projects", "description": "List projects"},
            {"command": "project", "description": "Switch active project"},
            {"command": "newproject", "description": "Create project"},
            {"command": "newrepo", "description": "Create GitHub repository for active project"},
            {"command": "repo", "description": "Bind existing GitHub repository to active project"},
            {"command": "onboard", "description": "Run project onboarding for active project"},
            {"command": "bootstrap", "description": "Preset flow: repo -> onboard -> backlog -> execute"},
            {"command": "sessions", "description": "List active sessions"},
            {"command": "session", "description": "Bind chat to session id"},
            {"command": "new", "description": "Create and bind new session"},
            {"command": "run", "description": "Run worker default entry"},
            {"command": "stop", "description": "Stop active worker runs"},
            {"command": "cancel", "description": "Cancel current queen turn"},
            {"command": "retention", "description": "Retention status for active project"},
            {"command": "digest", "description": "Retention digest across projects"},
            {"command": "autodigest", "description": "Autonomous cycle digest across projects"},
            {"command": "toolchain", "description": "Toolchain profile status for active project"},
            {"command": "toolchain_plan", "description": "Plan toolchain profile (optional source arg)"},
            {"command": "toolchain_approve", "description": "Approve pending toolchain token"},
            {"command": "credentials", "description": "Credential readiness report"},
            {"command": "toggle", "description": "Toggle button menu"},
            {"command": "help", "description": "Show usage help"},
        ]
        try:
            await self._api("setMyCommands", {"commands": commands})
            # Ensure command hints are visible in private chats regardless of locale settings.
            await self._api(
                "setMyCommands",
                {
                    "commands": commands,
                    "scope": {"type": "all_private_chats"},
                    "language_code": "en",
                },
            )
            await self._api("setChatMenuButton", {"menu_button": {"type": "commands"}})
            self._commands_initialized = True
            logger.info("Telegram bridge commands registered (%d)", len(commands))
        except Exception:
            logger.exception("Telegram bridge failed to register command hints")

    @staticmethod
    def _main_reply_keyboard() -> dict[str, Any]:
        return {
            "keyboard": [
                [
                    TelegramBridge.MENU_PROJECTS,
                    TelegramBridge.MENU_STATUS,
                ],
                [
                    TelegramBridge.MENU_SESSIONS,
                    TelegramBridge.MENU_NEW,
                ],
                [
                    TelegramBridge.MENU_RUN,
                    TelegramBridge.MENU_STOP,
                ],
                [
                    TelegramBridge.MENU_CANCEL_TURN,
                    TelegramBridge.MENU_HELP,
                ],
                [
                    TelegramBridge.MENU_TOOLCHAIN,
                    TelegramBridge.MENU_CREDENTIALS,
                    TelegramBridge.MENU_TOGGLE,
                ],
            ],
            "resize_keyboard": True,
            "persistent": False,
            "input_field_placeholder": "Type message to Hive queen...",
        }

    @staticmethod
    def _hide_reply_keyboard() -> dict[str, Any]:
        return {"remove_keyboard": True}

    def _is_menu_visible(self, chat_id: str) -> bool:
        return self._menu_visible.get(chat_id, True)

    def _set_menu_visible(self, chat_id: str, visible: bool) -> None:
        self._menu_visible[chat_id] = visible
        self._persist_state()

    def _remember_chat(self, chat_id: str) -> None:
        if chat_id in self._known_chats:
            return
        self._known_chats.add(chat_id)
        self._persist_state()

    async def _send_text(
        self,
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        text = self._sanitize_text_for_telegram(text)
        max_len = 3900
        chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)] or [""]

        first = True
        for chunk in chunks:
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            }
            if first and reply_markup is not None:
                payload["reply_markup"] = reply_markup
            await self._api("sendMessage", payload)
            first = False

        logger.info("Telegram bridge sent message to chat=%s chars=%d", chat_id, len(text))

    async def _clear_inline_markup_from_callback(self, callback: dict[str, Any]) -> None:
        """Disable inline buttons on a callback source message after user selects an option."""
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        if chat_id is None or message_id is None:
            return
        try:
            await self._api(
                "editMessageReplyMarkup",
                {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": {"inline_keyboard": []},
                },
            )
        except Exception as exc:
            details = self._format_exception_details(exc)
            # Another click can race with already-cleared markup; this is not actionable.
            if "message is not modified" in details.lower():
                return
            logger.info(
                "Telegram bridge could not clear inline keyboard chat=%s message_id=%s: %s",
                chat_id,
                message_id,
                details,
            )

    @staticmethod
    def _sanitize_text_for_telegram(text: str) -> str:
        """Strip internal reasoning wrapper blocks from outbound snapshots."""
        cleaned = text or ""
        cleaned = re.sub(r"<situation>.*?</situation>\s*", "", cleaned, flags=re.DOTALL | re.I)
        cleaned = re.sub(r"<monologue>.*?</monologue>\s*", "", cleaned, flags=re.DOTALL | re.I)
        cleaned = cleaned.strip()
        return cleaned or text

    def _bind_chat(self, chat_id: str, session_id: str) -> None:
        prev = self._chat_session.get(chat_id)
        if prev and chat_id in self._session_chats.get(prev, set()):
            self._session_chats[prev].discard(chat_id)

        self._chat_session[chat_id] = session_id
        self._session_chats[session_id].add(chat_id)
        session = self._manager.get_session(session_id)
        if session is not None:
            self._set_project_for_chat(chat_id, getattr(session, "project_id", self._default_project_id()))

        # Reset duplicate guards when switching sessions.
        self._last_sent.pop((chat_id, session_id), None)
        self._last_input_sig.pop((chat_id, session_id), None)
        self._remember_chat(chat_id)
        self._persist_state()

    def _chats_for_session(self, session_id: str) -> set[str]:
        """Return bound chats for a session, with optional test-chat fallback auto-bind."""
        chats = self._session_chats.get(session_id, set())
        if chats:
            return chats
        fallback_chat_id = os.environ.get("HIVE_TELEGRAM_TEST_CHAT_ID", "").strip()
        if not fallback_chat_id:
            return chats
        self._bind_chat(fallback_chat_id, session_id)
        return self._session_chats.get(session_id, set())

    def _persist_state(self) -> None:
        try:
            state = {
                "chat_session": dict(self._chat_session),
                "chat_project": dict(self._chat_project),
                "menu_visible": dict(self._menu_visible),
                "known_chats": sorted(self._known_chats),
                "updated_at": time.time(),
            }
            state_dir = os.path.dirname(self._state_path)
            if state_dir:
                os.makedirs(state_dir, exist_ok=True)
            tmp_path = f"{self._state_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._state_path)
        except Exception:
            logger.exception("Telegram bridge failed to persist state")

    def _load_persistent_state(self) -> None:
        path = self._state_path
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            chat_session = data.get("chat_session")
            if isinstance(chat_session, dict):
                for chat_id_raw, session_id_raw in chat_session.items():
                    chat_id = str(chat_id_raw).strip()
                    session_id = str(session_id_raw).strip()
                    if not chat_id or not session_id:
                        continue
                    self._chat_session[chat_id] = session_id
                    self._session_chats[session_id].add(chat_id)
            chat_project = data.get("chat_project")
            if isinstance(chat_project, dict):
                for chat_id_raw, project_id_raw in chat_project.items():
                    chat_id = str(chat_id_raw).strip()
                    project_id = str(project_id_raw).strip()
                    if chat_id and project_id:
                        self._chat_project[chat_id] = project_id
            menu_visible = data.get("menu_visible")
            if isinstance(menu_visible, dict):
                for chat_id_raw, visible_raw in menu_visible.items():
                    chat_id = str(chat_id_raw).strip()
                    if not chat_id:
                        continue
                    self._menu_visible[chat_id] = bool(visible_raw)
            known = data.get("known_chats")
            if isinstance(known, list):
                self._known_chats.update(str(chat_id).strip() for chat_id in known if str(chat_id).strip())
            logger.info(
                "Telegram bridge restored state: chats=%d, bindings=%d",
                len(self._known_chats),
                len(self._chat_session),
            )
        except Exception:
            logger.exception("Telegram bridge failed to load persistent state")

    def _pick_default_session(self) -> str | None:
        forced = os.environ.get("HIVE_TELEGRAM_BRIDGE_DEFAULT_SESSION", "").strip()
        if forced and self._manager.get_session(forced) is not None:
            return forced

        sessions = self._manager.list_sessions()
        if not sessions:
            return None
        sessions.sort(key=lambda s: getattr(s, "loaded_at", 0.0), reverse=True)
        return sessions[0].id

    def _pick_default_session_for_project(self, project_id: str) -> str | None:
        sessions = self._manager.list_sessions(project_id=project_id)
        if not sessions:
            return None
        sessions.sort(key=lambda s: getattr(s, "loaded_at", 0.0), reverse=True)
        return sessions[0].id

    async def _ensure_session(self) -> str:
        sid = self._pick_default_session()
        if sid:
            return sid
        session = await self._manager.create_session(project_id=self._default_project_id())
        return session.id

    async def _ensure_session_for_project(self, project_id: str) -> str:
        sid = self._pick_default_session_for_project(project_id)
        if sid:
            return sid
        session = await self._manager.create_session(project_id=project_id)
        return session.id

    async def _ensure_bound_session(self, chat_id: str) -> tuple[str, Any]:
        session_id = self._chat_session.get(chat_id)
        if not session_id:
            project_id = self._selected_project_id(chat_id)
            session_id = await self._ensure_session_for_project(project_id)
            self._bind_chat(chat_id, session_id)

        session = self._manager.get_session(session_id)
        if session is None:
            session = await self._manager.create_session(project_id=self._selected_project_id(chat_id))
            session_id = session.id
            self._bind_chat(chat_id, session_id)

        # Ensure this session is subscribed immediately, so Web-originated
        # user input is mirrored to bound Telegram chats without waiting
        # for the periodic sync loop.
        try:
            if getattr(session, "event_bus", None) is not None:
                await self._subscribe_session(session)
        except Exception:
            logger.exception("Telegram bridge failed to subscribe session=%s", session_id)

        return session_id, session

    async def _inject_user_input(self, chat_id: str, text: str) -> None:
        session_id, session = await self._ensure_bound_session(chat_id)

        node = await self._await_queen_node(session, timeout_s=10.0)
        if node is None:
            queen_task = getattr(session, "queen_task", None)
            if queen_task is not None and not queen_task.done():
                node = await self._await_queen_node(session, timeout_s=8.0)
            else:
                await self._manager.revive_queen(session)
                node = await self._await_queen_node(session, timeout_s=10.0)

        if node is None or not hasattr(node, "inject_event"):
            await self._send_text(chat_id, "Queen is not ready yet. Try again in a moment.")
            return

        await node.inject_event(text, is_client_input=True)
        logger.info("Telegram bridge injected chat=%s into session=%s", chat_id, session_id)
        await session.event_bus.publish(
            AgentEvent(
                type=EventType.CLIENT_INPUT_RECEIVED,
                stream_id="queen",
                node_id="queen",
                execution_id=session.id,
                data={"content": text, "source": "telegram", "chat_id": chat_id},
            )
        )

    async def _await_queen_node(self, session: Any, *, timeout_s: float = 3.0) -> Any | None:
        """Wait briefly until queen executor + node are available."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(timeout_s, 0.1)

        while loop.time() < deadline:
            executor = session.queen_executor
            node = executor.node_registry.get("queen") if executor is not None else None
            if node is not None and hasattr(node, "inject_event"):
                return node
            await asyncio.sleep(0.1)

        return None

    def _register_callback(
        self,
        *,
        chat_id: str,
        action: str,
        payload: dict[str, Any] | None = None,
        group_id: str | None = None,
        ttl_s: int = 900,
    ) -> str:
        token = uuid.uuid4().hex[:12]
        self._callback_payloads[token] = {
            "chat_id": chat_id,
            "action": action,
            "payload": payload or {},
            "expires_at": time.time() + ttl_s,
            "group_id": group_id or "",
        }
        if group_id:
            self._callback_groups.setdefault(group_id, set()).add(token)
        return f"hcb:{token}"

    def _consume_callback(self, chat_id: str, data: str) -> tuple[str, dict[str, Any]] | None:
        if not data.startswith("hcb:"):
            return None
        token = data.split(":", 1)[1].strip()
        entry = self._callback_payloads.pop(token, None)
        if not entry:
            return None
        if entry.get("chat_id") != chat_id:
            return None
        if float(entry.get("expires_at", 0.0)) < time.time():
            return None
        group_id = str(entry.get("group_id") or "").strip()
        if group_id:
            siblings = self._callback_groups.pop(group_id, set())
            for sibling in siblings:
                if sibling != token:
                    self._callback_payloads.pop(sibling, None)
        return str(entry.get("action") or ""), dict(entry.get("payload") or {})

    def _make_inline_markup(
        self,
        *,
        chat_id: str,
        rows: list[list[tuple[str, str, dict[str, Any] | None]]],
        single_use_group: bool = True,
        ttl_s: int = 900,
    ) -> dict[str, Any]:
        inline_keyboard: list[list[dict[str, str]]] = []
        group_id = uuid.uuid4().hex[:10] if single_use_group else None
        for row in rows:
            out_row: list[dict[str, str]] = []
            for label, action, payload in row:
                cb = self._register_callback(
                    chat_id=chat_id,
                    action=action,
                    payload=payload or {},
                    group_id=group_id,
                    ttl_s=ttl_s,
                )
                out_row.append({"text": label, "callback_data": cb})
            if out_row:
                inline_keyboard.append(out_row)
        return {"inline_keyboard": inline_keyboard}

    def _prune_state(self) -> None:
        now = time.time()
        for token in [k for k, v in self._callback_payloads.items() if v.get("expires_at", 0) < now]:
            self._callback_payloads.pop(token, None)
        if self._callback_groups:
            live_tokens = set(self._callback_payloads.keys())
            for group_id, members in list(self._callback_groups.items()):
                members.intersection_update(live_tokens)
                if not members:
                    self._callback_groups.pop(group_id, None)
        for cbid in [k for k, expires_at in self._seen_callback_ids.items() if expires_at < now]:
            self._seen_callback_ids.pop(cbid, None)
        for chat_id in [
            k for k, v in self._pending_choice.items() if float(v.get("expires_at", 0.0)) < now
        ]:
            self._pending_choice.pop(chat_id, None)
        for chat_id in [
            k for k, v in self._pending_questions.items() if float(v.get("expires_at", 0.0)) < now
        ]:
            self._pending_questions.pop(chat_id, None)
        for chat_id in [
            k for k, v in self._pending_new_project.items() if float(v.get("expires_at", 0.0)) < now
        ]:
            self._pending_new_project.pop(chat_id, None)
        for chat_id in [
            k for k, v in self._pending_new_repo.items() if float(v.get("expires_at", 0.0)) < now
        ]:
            self._pending_new_repo.pop(chat_id, None)
        for chat_id in [
            k for k, v in self._pending_bootstrap.items() if float(v.get("expires_at", 0.0)) < now
        ]:
            self._pending_bootstrap.pop(chat_id, None)

    async def _send_help(self, chat_id: str) -> None:
        sid, session = await self._ensure_bound_session(chat_id)
        has_worker = bool(getattr(session, "graph_runtime", None))
        project_id = self._selected_project_id(chat_id)
        text = (
            "Hive Telegram Control Center\n\n"
            f"Project: {project_id}\n"
            f"Current session: {sid}\n"
            f"Worker loaded: {'yes' if has_worker else 'no'}\n\n"
            "How to use:\n"
            "1) Send any text to chat with queen.\n"
            "2) Use menu buttons for status/sessions/run control.\n"
            "3) When queen asks a question, tap inline options.\n\n"
            "Commands:\n"
            "/projects /project <id> /newproject <name>\n"
            "/newrepo <name> [owner=<org>] [visibility=private|public|internal]\n"
            "/repo <url|owner/repo> /onboard [stack=<..>] [template_id=<..>] [workspace_path=<..>]\n"
            "/bootstrap newrepo <name> [owner=<org>] [visibility=<..>] --task <goal> [--title <..>] [--criteria a|b|c]\n"
            "/bootstrap repo <url|owner/repo> --task <goal> [--title <..>] [--criteria a|b|c]\n"
            "/menu /help /status /sessions /session <id> /new\n"
            "/run /stop /cancel /retention /digest /autodigest\n"
            "/toolchain /toolchain_plan [workspace|repo-url] /toolchain_approve [token]\n"
            "/credentials (/creds)\n"
            "/hide /show /toggle"
        )
        markup = self._main_reply_keyboard() if self._is_menu_visible(chat_id) else None
        await self._send_text(chat_id, text, reply_markup=markup)

    def _project_retention_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        projects = self._manager.list_projects()
        for p in projects:
            project_id = str(p.get("id") or "")
            if not project_id:
                continue
            retention = resolve_retention_policy(p)
            effective = retention.get("effective", {})
            history_days = int(effective.get("history_days") or 30)
            min_keep = int(effective.get("min_sessions_to_keep") or 20)
            live_ids = {s.id for s in self._manager.list_sessions(project_id=project_id)}
            plan = build_retention_plan(
                project_id=project_id,
                history_days=history_days,
                min_sessions_to_keep=min_keep,
                live_session_ids=live_ids,
            )
            rows.append(
                {
                    "project_id": project_id,
                    "name": str(p.get("name") or project_id),
                    "eligible_count": int(plan.get("eligible_count") or 0),
                    "historical_sessions": int(plan.get("historical_sessions") or 0),
                    "history_days": history_days,
                }
            )
        rows.sort(key=lambda x: (x["eligible_count"], x["historical_sessions"]), reverse=True)
        return rows

    async def _send_retention_status(self, chat_id: str) -> None:
        project_id = self._selected_project_id(chat_id)
        project = self._manager.get_project(project_id)
        if project is None:
            await self._send_text(chat_id, f"Project not found: {project_id}")
            return
        retention = resolve_retention_policy(project)
        effective = retention.get("effective", {})
        history_days = int(effective.get("history_days") or 30)
        min_keep = int(effective.get("min_sessions_to_keep") or 20)
        live_ids = {s.id for s in self._manager.list_sessions(project_id=project_id)}
        plan = build_retention_plan(
            project_id=project_id,
            history_days=history_days,
            min_sessions_to_keep=min_keep,
            live_session_ids=live_ids,
        )
        lines = [
            f"Retention status: {project_id}",
            f"history_days={history_days}",
            f"min_sessions_to_keep={min_keep}",
            f"archive_enabled={bool(effective.get('archive_enabled', True))}",
            f"historical_sessions={int(plan.get('historical_sessions') or 0)}",
            f"eligible_now={int(plan.get('eligible_count') or 0)}",
        ]
        candidates = plan.get("candidates") or []
        if isinstance(candidates, list) and candidates:
            lines.append("")
            lines.append("Top candidates:")
            for item in candidates[:10]:
                sid = str(item.get("session_id") or "")
                age = float(item.get("age_days") or 0.0)
                lines.append(f"- {sid} ({int(round(age))}d)")
        await self._send_text(chat_id, "\n".join(lines))

    async def _send_retention_digest(self, chat_id: str, *, proactive: bool = False) -> bool:
        rows = self._project_retention_rows()
        risky = [r for r in rows if int(r.get("eligible_count") or 0) > 0]
        if proactive and not risky:
            return False
        lines = ["Retention digest"]
        if proactive:
            lines[0] = "Daily retention digest"
        lines.append("")
        if not rows:
            lines.append("No projects found.")
            await self._send_text(chat_id, "\n".join(lines))
            return True
        for row in rows[:12]:
            lines.append(
                f"- {row['project_id']} ({row['name']}): eligible={row['eligible_count']}, "
                f"historical={row['historical_sessions']}, days={row['history_days']}"
            )
        if risky:
            lines.append("")
            lines.append(f"Projects with retention backlog: {len(risky)}")
            lines.append("Use /retention after /project <id> for details.")
        await self._send_text(chat_id, "\n".join(lines))
        return True

    async def _send_autonomous_digest(self, chat_id: str, *, proactive: bool = False) -> bool:
        if self._client is None:
            await self._send_text(chat_id, "Bridge client not ready yet.")
            return False

        project_ids = [str(p.get("id") or "").strip() for p in self._manager.list_projects()]
        project_ids = [x for x in project_ids if x]
        if not project_ids:
            await self._send_text(chat_id, "No projects found.")
            return True

        core_api_base = os.environ.get("HIVE_TELEGRAM_LOCAL_API_BASE", "").strip()
        if not core_api_base:
            port = os.environ.get("HIVE_CORE_PORT", "8787").strip() or "8787"
            core_api_base = f"http://127.0.0.1:{port}/api"
        url = f"{core_api_base.rstrip('/')}/autonomous/loop/run-cycle/report"
        payload = {"project_ids": project_ids, "auto_start": False, "max_steps_per_project": 1}

        try:
            async with self._client.post(url, json=payload, timeout=20) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    await self._send_text(chat_id, f"Autonomous digest failed ({resp.status}).")
                    return False
        except Exception as e:
            await self._send_text(chat_id, f"Autonomous digest unreachable: {e}")
            return False

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            await self._send_text(chat_id, "Autonomous digest payload is not valid JSON.")
            return False

        summary = data.get("summary", {}) if isinstance(data, dict) else {}
        outcomes = summary.get("outcomes", {}) if isinstance(summary, dict) else {}
        projects = data.get("projects", []) if isinstance(data, dict) else []
        highlights = data.get("highlights", {}) if isinstance(data, dict) else {}
        if proactive and isinstance(outcomes, dict):
            noisy = int(outcomes.get("failed", 0)) + int(outcomes.get("escalated", 0)) + int(outcomes.get("manual_deferred", 0))
            if noisy <= 0:
                return False

        lines = ["Autonomous cycle digest", ""]
        lines.append(
            f"projects={summary.get('projects_total', 0)} ok={summary.get('ok', 0)} failed={summary.get('failed', 0)}"
        )
        if isinstance(outcomes, dict) and outcomes:
            pairs = [f"{k}:{v}" for k, v in sorted(outcomes.items(), key=lambda item: str(item[0]))]
            lines.append("outcomes: " + ", ".join(pairs))
        ready = highlights.get("terminal_ready_projects", []) if isinstance(highlights, dict) else []
        blocked = highlights.get("blocked_projects", []) if isinstance(highlights, dict) else []
        deferred = highlights.get("manual_deferred_projects", []) if isinstance(highlights, dict) else []
        if isinstance(ready, list) and ready:
            lines.append("ready_for_pr: " + ", ".join(str(x) for x in ready[:8]))
        if isinstance(blocked, list) and blocked:
            lines.append("blocked: " + ", ".join(str(x) for x in blocked[:8]))
        if isinstance(deferred, list) and deferred:
            lines.append("manual_deferred: " + ", ".join(str(x) for x in deferred[:8]))
        if isinstance(projects, list) and projects:
            lines.append("")
            lines.append("Projects:")
            for row in projects[:12]:
                if not isinstance(row, dict):
                    continue
                pid = str(row.get("project_id") or "")
                outcome = str(row.get("outcome") or "-")
                term = str(row.get("terminal_status") or "-")
                pr_ready = bool(row.get("pr_ready"))
                lines.append(f"- {pid}: outcome={outcome}, terminal={term}, pr_ready={pr_ready}")
        lines.append("")
        lines.append("Next actions:")
        if isinstance(blocked, list) and blocked:
            lines.append("1) Open blocked projects and resolve failed/escalated stages.")
        else:
            lines.append("1) No blocked projects detected.")
        if isinstance(deferred, list) and deferred:
            lines.append("2) Run manual evaluate for deferred projects.")
        else:
            lines.append("2) No manual deferred actions pending.")
        if isinstance(ready, list) and ready:
            lines.append("3) Prepare PR/update report for ready projects.")
        else:
            lines.append("3) Continue cycle until projects become PR-ready.")

        await self._send_text(chat_id, "\n".join(lines))
        return True

    def _core_api_base(self) -> str:
        base = os.environ.get("HIVE_TELEGRAM_LOCAL_API_BASE", "").strip()
        if not base:
            port = os.environ.get("HIVE_CORE_PORT", "8787").strip() or "8787"
            base = f"http://127.0.0.1:{port}/api"
        return base.rstrip("/")

    async def _core_api_json(
        self,
        *,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: int = 25,
    ) -> tuple[int, dict[str, Any]]:
        if self._client is None:
            raise RuntimeError("Bridge client not ready")
        url = f"{self._core_api_base()}{path}"
        req_method = method.strip().upper()
        if req_method == "GET":
            async with self._client.get(url, timeout=timeout) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    data = {"raw": text}
                return int(resp.status), data if isinstance(data, dict) else {"data": data}
        async with self._client.post(url, json=payload or {}, timeout=timeout) as resp:
            text = await resp.text()
            try:
                data = json.loads(text) if text else {}
            except json.JSONDecodeError:
                data = {"raw": text}
            return int(resp.status), data if isinstance(data, dict) else {"data": data}

    @staticmethod
    def _parse_toolchain_source_arg(raw: str) -> tuple[str | None, str | None]:
        arg = raw.strip()
        if not arg:
            return None, None
        if arg.startswith("workspace="):
            value = arg.split("=", 1)[1].strip()
            return (value or None), None
        if arg.startswith("repo=") or arg.startswith("repository="):
            value = arg.split("=", 1)[1].strip()
            return None, (value or None)
        if re.match(r"^(https?://|git@|ssh://)", arg):
            return None, arg
        return arg, None

    async def _send_toolchain_status(self, chat_id: str) -> None:
        project_id = self._selected_project_id(chat_id)
        path = f"/projects/{quote(project_id, safe='')}/toolchain-profile"
        try:
            status, data = await self._core_api_json(method="GET", path=path)
        except Exception as e:
            await self._send_text(chat_id, f"Toolchain status unavailable: {e}")
            return
        if status >= 400:
            err = str(data.get("error") or f"HTTP {status}")
            await self._send_text(chat_id, f"Toolchain status failed: {err}")
            return

        profile = data.get("toolchain_profile") if isinstance(data, dict) else {}
        profile = profile if isinstance(profile, dict) else {}
        pending = profile.get("pending_plan") if isinstance(profile.get("pending_plan"), dict) else {}
        pending_plan = pending.get("plan") if isinstance(pending.get("plan"), dict) else {}
        approved = profile.get("approved_plan") if isinstance(profile.get("approved_plan"), dict) else {}
        source = pending.get("source") if isinstance(pending.get("source"), dict) else {}
        pending_token = str(pending_plan.get("confirm_token") or "").strip()
        lines = [f"Toolchain profile: {project_id}", ""]
        if source:
            ws = str(source.get("workspace_path") or "").strip()
            repo = str(source.get("repository") or "").strip()
            if ws:
                lines.append(f"source.workspace={ws}")
            if repo:
                lines.append(f"source.repository={repo}")
        if pending_plan:
            lines.append("pending_plan=yes")
            lines.append(f"pending.fingerprint={pending_plan.get('plan_fingerprint', '--')}")
            lines.append(f"pending.stack={pending_plan.get('recommended_stack', '--')}")
            toolchains = pending_plan.get("toolchains") or []
            if isinstance(toolchains, list):
                lines.append("pending.toolchains=" + (", ".join(str(x) for x in toolchains) or "--"))
            if pending_token:
                lines.append(f"pending.token={pending_token}")
        else:
            lines.append("pending_plan=no")
        if approved:
            plan = approved.get("plan") if isinstance(approved.get("plan"), dict) else {}
            lines.append("approved_plan=yes")
            lines.append(f"approved.fingerprint={plan.get('plan_fingerprint', '--')}")
            lines.append(f"approved.token={approved.get('approved_token', '--')}")
        else:
            lines.append("approved_plan=no")

        rows: list[list[tuple[str, str, dict[str, Any] | None]]] = [
            [("🧰 Plan", "plan_toolchain", None), ("🔄 Refresh", "show_toolchain", None)],
        ]
        if pending_token:
            rows.append([("✅ Approve Pending", "approve_toolchain", {"token": pending_token})])
        await self._send_text(
            chat_id,
            "\n".join(lines),
            reply_markup=self._make_inline_markup(chat_id=chat_id, rows=rows),
        )

    async def _send_credentials_readiness(self, chat_id: str) -> None:
        try:
            status, data = await self._core_api_json(
                method="GET",
                path="/credentials/readiness?bundle=local_pro_stack",
            )
        except Exception as e:
            await self._send_text(chat_id, f"Credential readiness unavailable: {e}")
            return
        if status >= 400:
            err = str(data.get("error") or f"HTTP {status}")
            await self._send_text(chat_id, f"Credential readiness failed: {err}")
            return

        summary = data.get("summary") if isinstance(data, dict) else {}
        summary = summary if isinstance(summary, dict) else {}
        missing = data.get("missing") if isinstance(data, dict) else {}
        missing = missing if isinstance(missing, dict) else {}
        providers = data.get("providers") if isinstance(data, dict) else []
        providers = providers if isinstance(providers, list) else []

        lines = [
            f"Credential readiness ({str(data.get('bundle') or 'local_pro_stack')})",
            "",
            (
                f"required: {int(summary.get('required_available') or 0)}"
                f"/{int(summary.get('required_total') or 0)}"
                f" (missing={int(summary.get('required_missing') or 0)})"
            ),
            (
                f"optional: {int(summary.get('optional_available') or 0)}"
                f"/{int(summary.get('optional_total') or 0)}"
                f" (missing={int(summary.get('optional_missing') or 0)})"
            ),
            f"ready: {'yes' if bool(summary.get('ready')) else 'no'}",
        ]

        missing_required = [str(x) for x in (missing.get("required") or []) if str(x).strip()]
        missing_optional = [str(x) for x in (missing.get("optional") or []) if str(x).strip()]
        if missing_required:
            lines.append("")
            lines.append("Missing required:")
            for var_name in missing_required[:12]:
                lines.append(f"- {var_name}")
        if missing_optional:
            lines.append("")
            lines.append("Missing optional:")
            for var_name in missing_optional[:8]:
                lines.append(f"- {var_name}")

        provider_missing = [
            row
            for row in providers
            if isinstance(row, dict) and int(row.get("credentials_missing") or 0) > 0
        ]
        if provider_missing:
            lines.append("")
            lines.append("Providers with gaps:")
            for row in provider_missing[:10]:
                lines.append(
                    f"- {row.get('provider')}: missing "
                    f"{int(row.get('credentials_missing') or 0)}/{int(row.get('credentials_total') or 0)}"
                )

        await self._send_text(chat_id, "\n".join(lines))

    async def _plan_project_toolchain(
        self,
        chat_id: str,
        *,
        workspace_path: str | None = None,
        repository: str | None = None,
    ) -> None:
        project_id = self._selected_project_id(chat_id)
        payload: dict[str, Any] = {}
        if workspace_path:
            payload["workspace_path"] = workspace_path
        if repository:
            payload["repository"] = repository
        path = f"/projects/{quote(project_id, safe='')}/toolchain-profile/plan"
        try:
            status, data = await self._core_api_json(method="POST", path=path, payload=payload)
        except Exception as e:
            await self._send_text(chat_id, f"Toolchain plan failed: {e}")
            return
        if status >= 400:
            err = str(data.get("error") or f"HTTP {status}")
            await self._send_text(chat_id, f"Toolchain plan rejected: {err}")
            return
        pending = data.get("pending_plan") if isinstance(data.get("pending_plan"), dict) else {}
        plan = pending.get("plan") if isinstance(pending.get("plan"), dict) else {}
        instructions = data.get("instructions") if isinstance(data.get("instructions"), dict) else {}
        token = str(plan.get("confirm_token") or "").strip()
        lines = [
            f"Toolchain plan ready: {project_id}",
            f"fingerprint={plan.get('plan_fingerprint', '--')}",
            f"stack={plan.get('recommended_stack', '--')}",
            "toolchains=" + ", ".join(str(x) for x in (plan.get("toolchains") or [])),
            f"token={token or '--'}",
        ]
        env_exports = instructions.get("env_exports")
        if isinstance(env_exports, list) and env_exports:
            lines.append("env: " + " ; ".join(str(x) for x in env_exports))
        preview_cmd = str(instructions.get("preview_command") or "").strip()
        apply_cmd = str(instructions.get("apply_command") or "").strip()
        if preview_cmd:
            lines.append(f"preview={preview_cmd}")
        if apply_cmd:
            lines.append(f"apply={apply_cmd}")
        rows: list[list[tuple[str, str, dict[str, Any] | None]]] = [
            [("🔁 Re-plan", "plan_toolchain", {"workspace_path": workspace_path, "repository": repository})],
        ]
        if token:
            rows.append([("✅ Approve", "approve_toolchain", {"token": token})])
        await self._send_text(
            chat_id,
            "\n".join(lines),
            reply_markup=self._make_inline_markup(chat_id=chat_id, rows=rows),
        )

    async def _approve_project_toolchain(
        self,
        chat_id: str,
        *,
        confirm_token: str | None = None,
    ) -> None:
        project_id = self._selected_project_id(chat_id)
        token = (confirm_token or "").strip()
        status_payload: dict[str, Any] = {}
        if not token:
            status_path = f"/projects/{quote(project_id, safe='')}/toolchain-profile"
            try:
                status_code, status_payload = await self._core_api_json(method="GET", path=status_path)
            except Exception as e:
                await self._send_text(chat_id, f"Toolchain approve failed: {e}")
                return
            if status_code >= 400:
                err = str(status_payload.get("error") or f"HTTP {status_code}")
                await self._send_text(chat_id, f"Toolchain status failed: {err}")
                return
            profile = status_payload.get("toolchain_profile")
            profile = profile if isinstance(profile, dict) else {}
            pending = profile.get("pending_plan")
            pending = pending if isinstance(pending, dict) else {}
            plan = pending.get("plan")
            plan = plan if isinstance(plan, dict) else {}
            token = str(plan.get("confirm_token") or "").strip()
            if not token:
                await self._send_text(chat_id, "No pending toolchain plan. Run /toolchain_plan first.")
                return
            markup = self._make_inline_markup(
                chat_id=chat_id,
                rows=[[("✅ Approve Pending", "approve_toolchain", {"token": token})]],
            )
            await self._send_text(chat_id, f"Pending token: {token}", reply_markup=markup)
            return

        approve_path = f"/projects/{quote(project_id, safe='')}/toolchain-profile/approve"
        try:
            status, data = await self._core_api_json(
                method="POST",
                path=approve_path,
                payload={"confirm_token": token, "revalidate": True},
            )
        except Exception as e:
            await self._send_text(chat_id, f"Toolchain approve failed: {e}")
            return
        if status >= 400:
            err = str(data.get("error") or f"HTTP {status}")
            new_pending = data.get("pending_plan") if isinstance(data.get("pending_plan"), dict) else {}
            new_plan = new_pending.get("plan") if isinstance(new_pending.get("plan"), dict) else {}
            new_token = str(new_plan.get("confirm_token") or "").strip()
            lines = [f"Toolchain approve rejected: {err}"]
            rows: list[list[tuple[str, str, dict[str, Any] | None]]] = []
            if new_token:
                lines.append(f"updated_token={new_token}")
                rows.append([("✅ Approve Updated", "approve_toolchain", {"token": new_token})])
            await self._send_text(
                chat_id,
                "\n".join(lines),
                reply_markup=self._make_inline_markup(chat_id=chat_id, rows=rows) if rows else None,
            )
            return
        instructions = data.get("instructions") if isinstance(data.get("instructions"), dict) else {}
        lines = [f"Toolchain plan approved: {project_id}", f"token={token}"]
        env_exports = instructions.get("env_exports")
        if isinstance(env_exports, list) and env_exports:
            lines.append("env: " + " ; ".join(str(x) for x in env_exports))
        preview_cmd = str(instructions.get("preview_command") or "").strip()
        apply_cmd = str(instructions.get("apply_command") or "").strip()
        if preview_cmd:
            lines.append(f"preview={preview_cmd}")
        if apply_cmd:
            lines.append(f"apply={apply_cmd}")
        await self._send_text(chat_id, "\n".join(lines))

    @staticmethod
    def _parse_newrepo_args(raw: str) -> tuple[dict[str, Any] | None, str | None]:
        text = raw.strip()
        if not text:
            return None, "Usage: /newrepo <name> [owner=<org>] [visibility=private|public|internal]"
        parts = [p for p in text.split() if p.strip()]
        if not parts:
            return None, "Usage: /newrepo <name> [owner=<org>] [visibility=private|public|internal]"
        name = parts[0].strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
            return None, "Repository name contains unsupported characters."
        owner: str | None = None
        visibility = "private"
        for token in parts[1:]:
            value = token.strip()
            if not value:
                continue
            lowered = value.lower()
            if lowered.startswith("owner="):
                owner_val = value.split("=", 1)[1].strip()
                if not owner_val or not re.fullmatch(r"[A-Za-z0-9_.-]+", owner_val):
                    return None, "owner must be a GitHub user/org slug."
                owner = owner_val
                continue
            if lowered.startswith("visibility="):
                vis_val = value.split("=", 1)[1].strip().lower()
                if vis_val not in {"private", "public", "internal"}:
                    return None, "visibility must be private, public, or internal."
                visibility = vis_val
                continue
            if lowered in {"private", "public", "internal"}:
                visibility = lowered
                continue
            return None, f"Unknown argument: {value}"
        return {"name": name, "owner": owner, "visibility": visibility}, None

    async def _plan_new_repository(
        self,
        chat_id: str,
        *,
        name: str,
        owner: str | None = None,
        visibility: str = "private",
    ) -> None:
        project_id = self._selected_project_id(chat_id)
        plan = {
            "project_id": project_id,
            "name": name,
            "owner": (owner or "").strip() or None,
            "visibility": visibility,
            "initialize_readme": True,
            "expires_at": time.time() + 900,
        }
        self._pending_new_repo[chat_id] = plan
        lines = [
            f"New repository plan: {project_id}",
            f"name={name}",
            f"owner={(owner or '--')}",
            f"visibility={visibility}",
            "ready_to_create=yes",
        ]
        markup = self._make_inline_markup(
            chat_id=chat_id,
            rows=[
                [("✅ Create Repository", "confirm_newrepo", None)],
                [("🚫 Cancel", "cancel_newrepo", None)],
            ],
        )
        await self._send_text(chat_id, "\n".join(lines), reply_markup=markup)

    async def _confirm_new_repository(self, chat_id: str) -> None:
        pending = self._pending_new_repo.get(chat_id)
        if not isinstance(pending, dict):
            await self._send_text(
                chat_id,
                "No pending repository plan. Run /newrepo <name> first.",
            )
            return
        project_id = str(pending.get("project_id") or "").strip() or self._selected_project_id(chat_id)
        path = f"/projects/{quote(project_id, safe='')}/repository/provision"
        payload: dict[str, Any] = {
            "name": str(pending.get("name") or "").strip(),
            "visibility": str(pending.get("visibility") or "private").strip().lower(),
            "initialize_readme": bool(pending.get("initialize_readme", True)),
        }
        owner = str(pending.get("owner") or "").strip()
        if owner:
            payload["owner"] = owner
        try:
            status, data = await self._core_api_json(method="POST", path=path, payload=payload)
        except Exception as e:
            await self._send_text(chat_id, f"Repository create failed: {e}")
            return
        if status >= 400:
            err = str(data.get("error") or f"HTTP {status}")
            await self._send_text(chat_id, f"Repository create rejected: {err}")
            return
        self._pending_new_repo.pop(chat_id, None)
        repo = data.get("repository") if isinstance(data.get("repository"), dict) else {}
        project = data.get("project") if isinstance(data.get("project"), dict) else {}
        full_name = str(repo.get("full_name") or payload["name"]).strip()
        html_url = str(repo.get("html_url") or "").strip()
        bound = str(project.get("repository") or html_url or full_name).strip()
        lines = [f"Repository created: {full_name}"]
        if html_url:
            lines.append(html_url)
        if bound:
            lines.append(f"project.repository={bound}")
        lines.append("Next: run /onboard or /toolchain_plan <repo-url>.")
        await self._send_text(chat_id, "\n".join(lines))

    async def _bind_project_repository(self, chat_id: str, *, repository: str) -> None:
        project_id = self._selected_project_id(chat_id)
        path = f"/projects/{quote(project_id, safe='')}/repository/bind"
        try:
            status, data = await self._core_api_json(
                method="POST",
                path=path,
                payload={"repository": repository},
            )
        except Exception as e:
            await self._send_text(chat_id, f"Repository bind failed: {e}")
            return
        if status >= 400:
            err = str(data.get("error") or f"HTTP {status}")
            await self._send_text(chat_id, f"Repository bind rejected: {err}")
            return
        repo = data.get("repository") if isinstance(data.get("repository"), dict) else {}
        project = data.get("project") if isinstance(data.get("project"), dict) else {}
        full_name = str(repo.get("full_name") or "").strip()
        html_url = str(repo.get("html_url") or "").strip()
        bound = str(project.get("repository") or html_url or full_name).strip()
        lines = [f"Repository bound: {full_name or bound}"]
        if html_url:
            lines.append(html_url)
        if bound:
            lines.append(f"project.repository={bound}")
        lines.append("Next: run /onboard or /toolchain_plan.")
        await self._send_text(chat_id, "\n".join(lines))

    @staticmethod
    def _parse_onboard_args(raw: str) -> tuple[dict[str, Any] | None, str | None]:
        arg = raw.strip()
        if not arg:
            return {}, None
        payload: dict[str, Any] = {}
        stack_set = False
        for token in [p for p in arg.split() if p.strip()]:
            value = token.strip()
            if "=" in value:
                key, val = value.split("=", 1)
                key = key.strip().lower()
                val = val.strip()
                if not key:
                    return None, f"Invalid onboarding argument: {value}"
                if key in {"stack"}:
                    payload["stack"] = val
                    stack_set = True
                    continue
                if key in {"template", "template_id"}:
                    payload["template_id"] = val
                    continue
                if key in {"workspace", "workspace_path"}:
                    payload["workspace_path"] = val
                    continue
                if key in {"repo", "repository"}:
                    payload["repository"] = val
                    continue
                if key in {"dry_run_command"}:
                    payload["dry_run_command"] = val
                    continue
                return None, f"Unknown onboarding argument: {key}"
            elif not stack_set:
                payload["stack"] = value
                stack_set = True
            else:
                return None, f"Unknown onboarding argument: {value}"
        return payload, None

    async def _run_project_onboarding(self, chat_id: str, *, payload: dict[str, Any] | None = None) -> None:
        project_id = self._selected_project_id(chat_id)
        path = f"/projects/{quote(project_id, safe='')}/onboarding"
        body = payload or {}
        await self._send_text(chat_id, "⏳ Running onboarding checks...")
        try:
            status, data = await self._core_api_json(method="POST", path=path, payload=body, timeout=90)
        except Exception as e:
            await self._send_text(chat_id, f"Onboarding failed: {e}")
            return
        if status >= 400:
            err = str(data.get("error") or f"HTTP {status}")
            await self._send_text(chat_id, f"Onboarding rejected: {err}")
            return
        ready = bool(data.get("ready"))
        checks = data.get("checks") if isinstance(data.get("checks"), list) else []
        total = len(checks)
        ok_count = sum(1 for c in checks if isinstance(c, dict) and str(c.get("status") or "") == "ok")
        warn_count = sum(1 for c in checks if isinstance(c, dict) and str(c.get("status") or "") == "warn")
        fail_count = sum(1 for c in checks if isinstance(c, dict) and str(c.get("status") or "") == "fail")
        manifest = data.get("manifest") if isinstance(data.get("manifest"), dict) else {}
        dry_run = data.get("dry_run") if isinstance(data.get("dry_run"), dict) else {}
        lines = [
            f"Onboarding report: {project_id}",
            f"ready={str(ready).lower()}",
            f"repository={str(data.get('repository') or '--')}",
            f"workspace={str(data.get('workspace_path') or '--')}",
            f"checks={ok_count}/{total} ok, warn={warn_count}, fail={fail_count}",
            f"manifest.exists={str(bool(manifest.get('exists'))).lower()}",
            f"dry_run.status={str(dry_run.get('status') or '--')}",
        ]
        if fail_count > 0:
            failed_ids = [
                str(c.get("id") or "")
                for c in checks
                if isinstance(c, dict) and str(c.get("status") or "") == "fail"
            ]
            failed_ids = [x for x in failed_ids if x]
            if failed_ids:
                lines.append("failed_checks=" + ", ".join(failed_ids[:6]))
        if ready:
            lines.append("Next: /toolchain_plan <repo-or-workspace> then /run.")
        else:
            lines.append("Next: fix failed checks, then re-run /onboard.")
        await self._send_text(chat_id, "\n".join(lines))

    @staticmethod
    def _strip_wrapping_quotes(text: str) -> str:
        value = (text or "").strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            return value[1:-1].strip()
        return value

    @staticmethod
    def _extract_flag_values(
        raw: str,
        *,
        allowed: set[str],
    ) -> tuple[str, dict[str, str], str | None]:
        pattern = re.compile(r"(?:^|\s)(--[a-z-]+)\s+")
        matches = list(pattern.finditer(raw))
        if not matches:
            return raw.strip(), {}, None

        head = raw[: matches[0].start()].strip()
        values: dict[str, str] = {}
        for idx, match in enumerate(matches):
            key = str(match.group(1) or "").strip()
            if key not in allowed:
                return head, values, f"Unsupported flag: {key}"
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
            value = raw[start:end].strip()
            if not value:
                return head, values, f"Missing value for {key}"
            if key in values:
                return head, values, f"Duplicate flag: {key}"
            values[key] = TelegramBridge._strip_wrapping_quotes(value)
        return head, values, None

    @staticmethod
    def _default_bootstrap_title(task_goal: str) -> str:
        text = (task_goal or "").strip()
        if not text:
            return "Bootstrap task"
        compact = re.sub(r"\s+", " ", text)
        return compact[:80].rstrip(" .,;:-") or "Bootstrap task"

    def _parse_bootstrap_args(self, raw: str) -> tuple[dict[str, Any] | None, str | None]:
        text = raw.strip()
        if not text:
            return None, (
                "Usage:\n"
                "/bootstrap newrepo <name> [owner=<org>] [visibility=private|public|internal] --task <goal>\n"
                "/bootstrap repo <url|owner/repo> --task <goal>"
            )

        head, flags, err = self._extract_flag_values(
            text,
            allowed={
                "--task",
                "--title",
                "--criteria",
                "--max-steps",
                "--priority",
                "--stack",
                "--template",
                "--workspace",
            },
        )
        if err:
            return None, err

        task_goal = str(flags.get("--task") or "").strip()
        if not task_goal:
            return None, "Flag --task is required."
        task_title = str(flags.get("--title") or self._default_bootstrap_title(task_goal)).strip()
        if not task_title:
            return None, "Task title cannot be empty."

        criteria_text = str(flags.get("--criteria") or "").strip()
        acceptance_criteria = [x.strip() for x in criteria_text.split("|") if x.strip()]
        if not acceptance_criteria:
            acceptance_criteria = [
                "Implementation is complete and consistent with the goal",
                "Relevant checks/tests pass",
                "Run report contains clear delivery summary",
            ]

        priority = str(flags.get("--priority") or "high").strip().lower()
        if priority not in {"low", "medium", "high", "critical"}:
            return None, "priority must be one of: low, medium, high, critical."

        max_steps_text = str(flags.get("--max-steps") or "12").strip()
        try:
            max_steps = int(max_steps_text)
        except ValueError:
            return None, "max-steps must be an integer."
        if max_steps < 1 or max_steps > 100:
            return None, "max-steps must be between 1 and 100."

        onboarding_payload: dict[str, Any] = {}
        stack = str(flags.get("--stack") or "").strip()
        if stack:
            onboarding_payload["stack"] = stack
        template_id = str(flags.get("--template") or "").strip()
        if template_id:
            onboarding_payload["template_id"] = template_id
        workspace_path = str(flags.get("--workspace") or "").strip()
        if workspace_path:
            onboarding_payload["workspace_path"] = workspace_path

        lowered_head = head.lower()
        plan: dict[str, Any] = {
            "task_title": task_title,
            "task_goal": task_goal,
            "acceptance_criteria": acceptance_criteria,
            "priority": priority,
            "max_steps": max_steps,
            "onboarding_payload": onboarding_payload,
        }
        if lowered_head.startswith("newrepo "):
            repo_args = head.split(" ", 1)[1].strip()
            newrepo, newrepo_err = self._parse_newrepo_args(repo_args)
            if newrepo is None:
                return None, newrepo_err or "Invalid newrepo bootstrap arguments."
            plan["mode"] = "newrepo"
            plan["newrepo"] = newrepo
            return plan, None
        if lowered_head.startswith("repo "):
            repository = head.split(" ", 1)[1].strip()
            if not repository:
                return None, "Usage: /bootstrap repo <url|owner/repo> --task <goal>"
            plan["mode"] = "repo"
            plan["repository"] = repository
            return plan, None
        return None, "Mode must be `newrepo` or `repo`."

    async def _plan_bootstrap_flow(self, chat_id: str, plan: dict[str, Any]) -> None:
        project_id = self._selected_project_id(chat_id)
        mode = str(plan.get("mode") or "").strip()
        if mode not in {"newrepo", "repo"}:
            await self._send_text(chat_id, "Bootstrap plan rejected: invalid mode.")
            return
        stored = dict(plan)
        stored["project_id"] = project_id
        stored["expires_at"] = time.time() + 1200
        self._pending_bootstrap[chat_id] = stored

        lines = [f"Bootstrap plan: {project_id}"]
        if mode == "newrepo":
            nr = plan.get("newrepo") if isinstance(plan.get("newrepo"), dict) else {}
            lines.append(f"mode=newrepo name={nr.get('name', '--')} owner={nr.get('owner') or '--'}")
            lines.append(f"visibility={nr.get('visibility', '--')}")
        else:
            lines.append(f"mode=repo repository={str(plan.get('repository') or '--')}")
        lines.append(f"task.title={str(plan.get('task_title') or '--')}")
        lines.append(f"task.goal={str(plan.get('task_goal') or '--')}")
        lines.append("task.criteria=" + " | ".join(str(x) for x in (plan.get("acceptance_criteria") or [])))
        lines.append(f"priority={str(plan.get('priority') or 'high')} max_steps={str(plan.get('max_steps') or 12)}")
        onboarding_payload = plan.get("onboarding_payload") if isinstance(plan.get("onboarding_payload"), dict) else {}
        if onboarding_payload:
            lines.append(f"onboard={json.dumps(onboarding_payload, ensure_ascii=False)}")
        lines.append("")
        lines.append("Flow:")
        lines.append("1) repository setup (create/bind)")
        lines.append("2) onboarding")
        lines.append("3) create first backlog task")
        lines.append("4) execute-next")

        await self._send_text(
            chat_id,
            "\n".join(lines),
            reply_markup=self._make_inline_markup(
                chat_id=chat_id,
                rows=[
                    [("✅ Run Bootstrap", "confirm_bootstrap", None)],
                    [("🚫 Cancel", "cancel_bootstrap", None)],
                ],
            ),
        )

    async def _execute_bootstrap_flow(self, chat_id: str) -> None:
        pending = self._pending_bootstrap.pop(chat_id, None)
        if not isinstance(pending, dict):
            await self._send_text(chat_id, "No pending bootstrap plan. Use /bootstrap first.")
            return

        project_id = str(pending.get("project_id") or "").strip() or self._selected_project_id(chat_id)
        mode = str(pending.get("mode") or "").strip()
        trace_id = f"bs_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        trace: dict[str, Any] = {
            "trace_id": trace_id,
            "project_id": project_id,
            "mode": mode,
        }
        await self._send_text(chat_id, f"Bootstrap started: trace={trace_id}")

        repository_for_task = ""
        repository_display = ""
        if mode == "newrepo":
            nr = pending.get("newrepo") if isinstance(pending.get("newrepo"), dict) else {}
            provision_payload: dict[str, Any] = {
                "name": str(nr.get("name") or "").strip(),
                "visibility": str(nr.get("visibility") or "private").strip().lower(),
                "initialize_readme": True,
            }
            owner = str(nr.get("owner") or "").strip()
            if owner:
                provision_payload["owner"] = owner
            path = f"/projects/{quote(project_id, safe='')}/repository/provision"
            status, data = await self._core_api_json(method="POST", path=path, payload=provision_payload, timeout=45)
            if status >= 400:
                err = str(data.get("error") or f"HTTP {status}")
                await self._send_text(chat_id, f"Bootstrap failed at step 1 (repository create): {err}")
                return
            repo = data.get("repository") if isinstance(data.get("repository"), dict) else {}
            repository_display = str(repo.get("html_url") or repo.get("full_name") or "").strip()
            repository_for_task = repository_display
        elif mode == "repo":
            repository_raw = str(pending.get("repository") or "").strip()
            path = f"/projects/{quote(project_id, safe='')}/repository/bind"
            status, data = await self._core_api_json(
                method="POST",
                path=path,
                payload={"repository": repository_raw},
                timeout=45,
            )
            if status >= 400:
                err = str(data.get("error") or f"HTTP {status}")
                await self._send_text(chat_id, f"Bootstrap failed at step 1 (repository bind): {err}")
                return
            repo = data.get("repository") if isinstance(data.get("repository"), dict) else {}
            repository_display = str(repo.get("html_url") or repo.get("full_name") or repository_raw).strip()
            repository_for_task = repository_raw
        else:
            await self._send_text(chat_id, "Bootstrap failed: invalid mode.")
            return
        trace["repository"] = repository_display or repository_for_task
        await self._send_text(chat_id, "Step 1/4 done: repository is configured.")

        onboarding_payload = pending.get("onboarding_payload") if isinstance(pending.get("onboarding_payload"), dict) else {}
        if repository_for_task:
            onboarding_payload = dict(onboarding_payload)
            onboarding_payload.setdefault("repository", repository_for_task)
        onboard_path = f"/projects/{quote(project_id, safe='')}/onboarding"
        await self._send_text(chat_id, "⏳ Step 2/4: running onboarding...")
        onboard_status, onboard_data = await self._core_api_json(
            method="POST",
            path=onboard_path,
            payload=onboarding_payload,
            timeout=90,
        )
        if onboard_status >= 400:
            err = str(onboard_data.get("error") or f"HTTP {onboard_status}")
            await self._send_text(chat_id, f"Bootstrap failed at step 2 (onboarding): {err}")
            return
        onboarding_ready = bool(onboard_data.get("ready"))
        trace["onboarding_ready"] = onboarding_ready
        trace["workspace_path"] = str(onboard_data.get("workspace_path") or "").strip()
        checks = onboard_data.get("checks") if isinstance(onboard_data.get("checks"), list) else []
        failed_checks = [
            str(c.get("id") or "")
            for c in checks
            if isinstance(c, dict) and str(c.get("status") or "").strip().lower() == "fail"
        ]
        trace["onboarding_failed_checks"] = [x for x in failed_checks if x]
        if not onboarding_ready:
            await self._send_text(
                chat_id,
                "Bootstrap stopped at step 2: onboarding is not ready.\n"
                f"failed_checks={', '.join(trace['onboarding_failed_checks']) or '--'}",
            )
            return
        await self._send_text(chat_id, "Step 2/4 done: onboarding is ready.")

        task_payload: dict[str, Any] = {
            "title": str(pending.get("task_title") or "").strip(),
            "goal": str(pending.get("task_goal") or "").strip(),
            "acceptance_criteria": list(pending.get("acceptance_criteria") or []),
            "priority": str(pending.get("priority") or "high").strip().lower() or "high",
        }
        if repository_for_task:
            task_payload["repository"] = repository_for_task
        task_path = f"/projects/{quote(project_id, safe='')}/autonomous/backlog"
        task_status, task_data = await self._core_api_json(method="POST", path=task_path, payload=task_payload, timeout=45)
        if task_status >= 400:
            err = str(task_data.get("error") or f"HTTP {task_status}")
            await self._send_text(chat_id, f"Bootstrap failed at step 3 (backlog create): {err}")
            return
        task_id = str(task_data.get("id") or "").strip()
        trace["task_id"] = task_id
        await self._send_text(chat_id, f"Step 3/4 done: backlog task created ({task_id}).")

        exec_payload: dict[str, Any] = {
            "max_steps": int(pending.get("max_steps") or 12),
            "auto_start": True,
            "summary": f"telegram_bootstrap trace={trace_id}",
        }
        if repository_for_task:
            exec_payload["repository"] = repository_for_task
        exec_path = f"/projects/{quote(project_id, safe='')}/autonomous/execute-next"
        await self._send_text(chat_id, "⏳ Step 4/4: running execute-next...")
        exec_status, exec_data = await self._core_api_json(method="POST", path=exec_path, payload=exec_payload, timeout=120)
        if exec_status >= 400:
            err = str(exec_data.get("error") or f"HTTP {exec_status}")
            await self._send_text(chat_id, f"Bootstrap failed at step 4 (execute-next): {err}")
            return

        selected_task = exec_data.get("selected_task") if isinstance(exec_data.get("selected_task"), dict) else {}
        selected_task_id = str(selected_task.get("id") or "").strip()
        run_id = str(exec_data.get("run_id") or "").strip()
        terminal = bool(exec_data.get("terminal"))
        terminal_status = str(exec_data.get("terminal_status") or "").strip() or None
        trace["selected_task_id"] = selected_task_id
        trace["run_id"] = run_id
        trace["terminal"] = terminal
        trace["terminal_status"] = terminal_status

        report_endpoint = ""
        pr_url = ""
        if run_id:
            report_endpoint = f"/api/projects/{project_id}/autonomous/runs/{run_id}/report"
            report_path = f"/projects/{quote(project_id, safe='')}/autonomous/runs/{quote(run_id, safe='')}/report"
            report_status, report_data = await self._core_api_json(method="GET", path=report_path, timeout=60)
            if report_status < 400:
                report = report_data.get("report") if isinstance(report_data.get("report"), dict) else {}
                pr = report.get("pr") if isinstance(report.get("pr"), dict) else {}
                pr_url = str(pr.get("url") or "").strip()
        trace["report_endpoint"] = report_endpoint
        trace["pr_url"] = pr_url

        lines = [
            f"Bootstrap completed: trace={trace_id}",
            f"project={project_id}",
            f"repository={trace.get('repository') or '--'}",
            f"task_id={task_id or '--'}",
            f"selected_task_id={selected_task_id or '--'}",
            f"run_id={run_id or '--'}",
            f"terminal={str(terminal).lower()} terminal_status={terminal_status or '--'}",
        ]
        if selected_task_id and task_id and selected_task_id != task_id:
            lines.append("warning=execute-next picked a different task than the one just created")
        if report_endpoint:
            lines.append(f"report={report_endpoint}")
        if pr_url:
            lines.append(f"pr={pr_url}")
        await self._send_text(chat_id, "\n".join(lines))

    async def _docker_lane_status_line(self, chat_id: str, *, project_id: str) -> str:
        path = f"/autonomous/ops/status?project_id={quote(project_id, safe='')}"
        try:
            status, data = await self._core_api_json(method="GET", path=path, timeout=8)
        except Exception:
            return "Docker lane: unknown"
        if status >= 400:
            return "Docker lane: unknown"
        runtime = data.get("runtime") if isinstance(data, dict) else {}
        runtime = runtime if isinstance(runtime, dict) else {}
        lane = runtime.get("docker_lane") if isinstance(runtime.get("docker_lane"), dict) else {}
        enabled = bool(lane.get("enabled"))
        ready = bool(lane.get("ready"))
        lane_status = str(lane.get("status") or ("ready" if ready else "disabled")).strip()
        reason = str(lane.get("reason") or "").strip()
        base = f"Docker lane: {'on' if enabled else 'off'} ({lane_status})"
        if reason:
            base += f"; reason={reason}"
        return base

    async def _send_status(self, chat_id: str) -> None:
        session_id, session = await self._ensure_bound_session(chat_id)
        project_id = self._selected_project_id(chat_id)
        phase = getattr(getattr(session, "phase_state", None), "phase", None) or (
            "staging" if session.graph_runtime else "planning"
        )
        graph_id = getattr(session, "graph_id", None) or "-"
        uptime = int(max(0.0, time.time() - float(getattr(session, "loaded_at", time.time()))))
        available_triggers = len(getattr(session, "available_triggers", {}) or {})
        active_triggers = len(getattr(session, "active_trigger_ids", set()) or set())
        docker_lane_line = await self._docker_lane_status_line(chat_id, project_id=project_id)

        text = (
            "Session status\n\n"
            f"Project: {project_id}\n"
            f"Session: {session_id}\n"
            f"Phase: {phase}\n"
            f"Graph: {graph_id}\n"
            f"Worker loaded: {'yes' if session.graph_runtime else 'no'}\n"
            f"Uptime: {uptime}s\n"
            f"Triggers: {active_triggers}/{available_triggers} active\n"
            f"{docker_lane_line}\n"
        )
        markup = self._make_inline_markup(
            chat_id=chat_id,
            rows=[
                [("📁 Projects", "show_projects", None), ("🧠 Sessions", "show_sessions", None)],
                [("🆕 New session", "new_session", None), ("📊 Status", "show_status", None)],
                [("▶️ Run", "run_worker", None), ("⏹ Stop", "stop_worker", None)],
                [("🗂 Retention", "show_retention", None), ("📦 Digest", "show_digest", None)],
                [("🧭 Auto Digest", "show_autodigest", None)],
                [("🧰 Toolchain", "show_toolchain", None)],
                [("❌ Cancel", "cancel_turn", None), ("ℹ️ Help", "show_help", None)],
                [("🙈 Hide menu", "hide_menu", None), ("📌 Show menu", "show_menu", None)],
            ],
        )
        await self._send_text(chat_id, text, reply_markup=markup)

    async def _send_sessions(self, chat_id: str) -> None:
        project_id = self._selected_project_id(chat_id)
        sessions = self._manager.list_sessions(project_id=project_id)
        if not sessions:
            await self._send_text(chat_id, f"No active sessions in project '{project_id}'.")
            return
        sessions.sort(key=lambda s: getattr(s, "loaded_at", 0.0), reverse=True)

        active = self._chat_session.get(chat_id)
        lines: list[str] = [f"Active sessions for project '{project_id}':"]
        rows: list[list[tuple[str, str, dict[str, Any] | None]]] = []
        for s in sessions[:12]:
            graph = getattr(s, "graph_id", None) or "-"
            marker = "✅" if s.id == active else "•"
            lines.append(f"{marker} {s.id} (graph={graph})")
            label = f"{'✅ ' if s.id == active else ''}{s.id[-10:]}"
            rows.append([(label, "bind_session", {"session_id": s.id})])

        rows.append([("📁 Projects", "show_projects", None), ("🆕 New", "new_session", None)])
        await self._send_text(
            chat_id,
            "\n".join(lines),
            reply_markup=self._make_inline_markup(chat_id=chat_id, rows=rows),
        )

    async def _send_projects(self, chat_id: str) -> None:
        projects = self._manager.list_projects()
        if not projects:
            await self._send_text(chat_id, "No projects found.")
            return
        active = self._selected_project_id(chat_id)
        lines: list[str] = ["Projects:"]
        rows: list[list[tuple[str, str, dict[str, Any] | None]]] = []
        for p in projects[:12]:
            pid = str(p.get("id") or "")
            name = str(p.get("name") or pid)
            marker = "✅" if pid == active else "•"
            lines.append(f"{marker} {pid} ({name})")
            rows.append(
                [((f"{'✅ ' if pid == active else ''}{name[:22]}"), "select_project", {"project_id": pid})]
            )
        rows.append([("🆕 New project", "new_project_start", None), ("📊 Status", "show_status", None)])
        await self._send_text(
            chat_id,
            "\n".join(lines),
            reply_markup=self._make_inline_markup(chat_id=chat_id, rows=rows),
        )

    async def _run_worker_default(self, chat_id: str) -> None:
        _, session = await self._ensure_bound_session(chat_id)
        if not session.graph_runtime:
            await self._send_text(
                chat_id,
                "No worker graph loaded in this session. Load/build an agent first in Hive.",
            )
            return

        entry_points = session.graph_runtime.get_entry_points()
        if not entry_points:
            await self._send_text(chat_id, "No entry points available for this worker.")
            return
        entry = next((ep for ep in entry_points if ep.id == "default"), entry_points[0])
        execution_id = await session.graph_runtime.trigger(
            entry.id,
            input_data={},
            session_state={"resume_session_id": session.id},
        )

        if session.queen_executor:
            node = session.queen_executor.node_registry.get("queen")
            if node is not None and hasattr(node, "cancel_current_turn"):
                node.cancel_current_turn()
        if session.phase_state is not None:
            await session.phase_state.switch_to_running(source="telegram")

        await self._send_text(
            chat_id,
            f"Worker started.\nentry_point={entry.id}\nexecution_id={execution_id}",
        )

    async def _stop_worker(self, chat_id: str) -> None:
        _, session = await self._ensure_bound_session(chat_id)
        if not session.graph_runtime:
            await self._send_text(chat_id, "No worker graph loaded in this session.")
            return

        runtime = session.graph_runtime
        cancelled: list[str] = []
        for graph_id in runtime.list_graphs():
            reg = runtime.get_graph_registration(graph_id)
            if reg is None:
                continue
            for _ep_id, stream in reg.streams.items():
                for executor in stream._active_executors.values():
                    for node in executor.node_registry.values():
                        if hasattr(node, "signal_shutdown"):
                            node.signal_shutdown()
                        if hasattr(node, "cancel_current_turn"):
                            node.cancel_current_turn()
                for exec_id in list(stream.active_execution_ids):
                    try:
                        ok = await stream.cancel_execution(
                            exec_id, reason="Execution paused from Telegram"
                        )
                        if ok:
                            cancelled.append(exec_id)
                    except Exception:
                        continue

        runtime.pause_timers()
        if session.phase_state is not None:
            await session.phase_state.switch_to_staging(source="telegram")

        if cancelled:
            await self._send_text(chat_id, f"Stopped worker runs: {len(cancelled)}")
        else:
            await self._send_text(chat_id, "No active worker execution found.")

    async def _cancel_queen_turn(self, chat_id: str) -> None:
        _, session = await self._ensure_bound_session(chat_id)
        queen_executor = session.queen_executor
        if queen_executor is None:
            await self._send_text(chat_id, "Queen is not active right now.")
            return
        node = queen_executor.node_registry.get("queen")
        if node is None or not hasattr(node, "cancel_current_turn"):
            await self._send_text(chat_id, "Queen node not ready for cancel.")
            return
        node.cancel_current_turn()
        await self._send_text(chat_id, "Current queen turn cancelled.")

    def _clear_pending_input_state(self, chat_id: str, session_id: str | None = None) -> None:
        self._pending_choice.pop(chat_id, None)
        self._pending_questions.pop(chat_id, None)
        self._pending_new_project.pop(chat_id, None)
        self._pending_new_repo.pop(chat_id, None)
        self._pending_bootstrap.pop(chat_id, None)
        if session_id:
            self._last_input_sig.pop((chat_id, session_id), None)

    async def _handle_command(self, chat_id: str, text: str) -> bool:
        cmd = text.strip()
        lowered = cmd.lower()

        # Reply-keyboard shortcuts
        if cmd == self.MENU_HELP:
            lowered = "/help"
        elif cmd == self.MENU_STATUS:
            lowered = "/status"
        elif cmd == self.MENU_SESSIONS:
            lowered = "/sessions"
        elif cmd == self.MENU_NEW:
            lowered = "/new"
        elif cmd == self.MENU_RUN:
            lowered = "/run"
        elif cmd == self.MENU_STOP:
            lowered = "/stop"
        elif cmd == self.MENU_CANCEL_TURN:
            lowered = "/cancel"
        elif cmd == self.MENU_TOGGLE:
            lowered = "/toggle"
        elif cmd == self.MENU_PROJECTS:
            lowered = "/projects"
        elif cmd == self.MENU_TOOLCHAIN:
            lowered = "/toolchain"
        elif cmd == self.MENU_CREDENTIALS:
            lowered = "/credentials"

        if lowered.startswith("/start") or lowered.startswith("/help"):
            sid = await self._ensure_session()
            self._bind_chat(chat_id, sid)
            await self._send_help(chat_id)
            return True

        if lowered == "/menu":
            self._set_menu_visible(chat_id, True)
            await self._send_text(
                chat_id,
                "Main menu ready.",
                reply_markup=self._main_reply_keyboard(),
            )
            return True

        if lowered == "/show":
            self._set_menu_visible(chat_id, True)
            await self._send_text(
                chat_id,
                "Menu buttons are visible.",
                reply_markup=self._main_reply_keyboard(),
            )
            return True

        if lowered == "/hide":
            self._set_menu_visible(chat_id, False)
            show_markup = self._make_inline_markup(
                chat_id=chat_id,
                rows=[[("📌 Show menu", "show_menu", None), ("ℹ️ Help", "show_help", None)]],
            )
            await self._send_text(
                chat_id,
                "Menu buttons hidden. Use /show or tap button below.",
                reply_markup=self._hide_reply_keyboard(),
            )
            await self._send_text(chat_id, "Quick actions:", reply_markup=show_markup)
            return True

        if lowered == "/toggle":
            if self._is_menu_visible(chat_id):
                self._set_menu_visible(chat_id, False)
                show_markup = self._make_inline_markup(
                    chat_id=chat_id,
                    rows=[[("📌 Show menu", "show_menu", None), ("ℹ️ Help", "show_help", None)]],
                )
                await self._send_text(
                    chat_id,
                    "Menu buttons hidden. Use /show, /toggle, or tap button below.",
                    reply_markup=self._hide_reply_keyboard(),
                )
                await self._send_text(chat_id, "Quick actions:", reply_markup=show_markup)
                return True

            self._set_menu_visible(chat_id, True)
            await self._send_text(
                chat_id,
                "Menu buttons are visible.",
                reply_markup=self._main_reply_keyboard(),
            )
            return True

        if lowered == "/status":
            await self._send_status(chat_id)
            return True

        if lowered == "/sessions":
            await self._send_sessions(chat_id)
            return True

        if lowered == "/projects":
            self._pending_new_project.pop(chat_id, None)
            self._pending_new_repo.pop(chat_id, None)
            self._pending_bootstrap.pop(chat_id, None)
            await self._send_projects(chat_id)
            return True

        if lowered.startswith("/project "):
            pid = cmd.split(" ", 1)[1].strip()
            if not pid:
                await self._send_text(chat_id, "Usage: /project <project_id>")
                return True
            if self._manager.get_project(pid) is None:
                await self._send_text(chat_id, f"Project not found: {pid}")
                return True
            self._set_project_for_chat(chat_id, pid)
            sid = await self._ensure_session_for_project(pid)
            self._bind_chat(chat_id, sid)
            self._clear_pending_input_state(chat_id, sid)
            await self._send_text(chat_id, f"Active project set to: {pid}")
            await self._send_status(chat_id)
            return True

        if lowered.startswith("/newproject "):
            name = cmd.split(" ", 1)[1].strip()
            if not name:
                await self._send_text(chat_id, "Usage: /newproject <name>")
                return True
            created = self._manager.create_project(name=name)
            pid = str(created.get("id") or "")
            self._set_project_for_chat(chat_id, pid)
            sid = await self._ensure_session_for_project(pid)
            self._bind_chat(chat_id, sid)
            self._clear_pending_input_state(chat_id, sid)
            await self._send_text(chat_id, f"Created project '{created.get('name')}' ({pid})")
            await self._send_status(chat_id)
            return True
        if lowered.startswith("/newrepo"):
            args = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
            parsed, err = self._parse_newrepo_args(args)
            if parsed is None:
                await self._send_text(chat_id, err or "Invalid /newrepo arguments.")
                return True
            await self._plan_new_repository(
                chat_id,
                name=str(parsed.get("name") or "").strip(),
                owner=str(parsed.get("owner") or "").strip() or None,
                visibility=str(parsed.get("visibility") or "private").strip().lower() or "private",
            )
            return True
        if lowered.startswith("/bootstrap"):
            args = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
            plan, err = self._parse_bootstrap_args(args)
            if plan is None:
                await self._send_text(chat_id, err or "Invalid /bootstrap arguments.")
                return True
            await self._plan_bootstrap_flow(chat_id, plan)
            return True
        if lowered.startswith("/repo "):
            repository = cmd.split(" ", 1)[1].strip()
            if not repository:
                await self._send_text(chat_id, "Usage: /repo <url|owner/repo>")
                return True
            await self._bind_project_repository(chat_id, repository=repository)
            return True
        if lowered.startswith("/onboard"):
            arg = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
            payload, err = self._parse_onboard_args(arg)
            if payload is None:
                await self._send_text(chat_id, err or "Invalid /onboard arguments.")
                return True
            await self._run_project_onboarding(chat_id, payload=payload)
            return True

        if lowered.startswith("/session "):
            sid = cmd.split(" ", 1)[1].strip()
            if not sid:
                await self._send_text(chat_id, "Usage: /session <session_id>")
                return True
            if self._manager.get_session(sid) is None:
                await self._send_text(chat_id, f"Session not found: {sid}")
                return True
            self._bind_chat(chat_id, sid)
            self._clear_pending_input_state(chat_id, sid)
            await self._send_text(chat_id, f"Bound to session: {sid}")
            await self._send_status(chat_id)
            return True

        if lowered == "/new":
            s = await self._manager.create_session(project_id=self._selected_project_id(chat_id))
            self._bind_chat(chat_id, s.id)
            self._clear_pending_input_state(chat_id, s.id)
            await self._send_text(chat_id, f"Created and bound new session: {s.id}")
            await self._send_status(chat_id)
            return True

        if lowered == "/run":
            await self._run_worker_default(chat_id)
            return True

        if lowered == "/stop":
            await self._stop_worker(chat_id)
            return True

        if lowered == "/cancel":
            await self._cancel_queen_turn(chat_id)
            return True

        if lowered == "/retention":
            await self._send_retention_status(chat_id)
            return True

        if lowered == "/digest":
            await self._send_retention_digest(chat_id, proactive=False)
            return True
        if lowered == "/autodigest":
            await self._send_autonomous_digest(chat_id, proactive=False)
            return True
        if lowered == "/toolchain":
            await self._send_toolchain_status(chat_id)
            return True
        if lowered.startswith("/toolchain_plan"):
            arg = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
            workspace_path, repository = self._parse_toolchain_source_arg(arg)
            await self._plan_project_toolchain(
                chat_id,
                workspace_path=workspace_path,
                repository=repository,
            )
            return True
        if lowered.startswith("/toolchain_approve"):
            token = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
            await self._approve_project_toolchain(chat_id, confirm_token=token or None)
            return True
        if lowered in {"/credentials", "/creds"}:
            await self._send_credentials_readiness(chat_id)
            return True

        return False

    async def _handle_callback_query(self, callback: dict[str, Any]) -> None:
        callback_id = str(callback.get("id") or "")
        from_user = callback.get("from") or {}
        if from_user.get("is_bot"):
            return

        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or "")
        data = str(callback.get("data") or "")
        if not chat_id:
            return
        self._remember_chat(chat_id)

        now = time.time()
        if callback_id and callback_id in self._seen_callback_ids:
            try:
                await self._api(
                    "answerCallbackQuery",
                    {
                        "callback_query_id": callback_id,
                        "text": "Already handled.",
                        "show_alert": False,
                    },
                )
            except Exception:
                logger.warning("Telegram bridge failed to answer duplicate callback query", exc_info=True)
            return
        if callback_id:
            self._seen_callback_ids[callback_id] = now + 600.0

        consumed = self._consume_callback(chat_id, data)
        if consumed is None:
            if callback_id:
                try:
                    await self._api(
                        "answerCallbackQuery",
                        {
                            "callback_query_id": callback_id,
                            "text": "This option is no longer active.",
                            "show_alert": False,
                        },
                    )
                except Exception:
                    logger.warning("Telegram bridge failed to answer stale callback query", exc_info=True)
            return
        if callback_id:
            try:
                await self._api("answerCallbackQuery", {"callback_query_id": callback_id})
            except Exception:
                logger.warning("Telegram bridge failed to answer callback query", exc_info=True)
        action, payload = consumed

        if action == "show_help":
            await self._send_help(chat_id)
            return
        if action == "show_menu":
            self._set_menu_visible(chat_id, True)
            await self._send_text(
                chat_id,
                "Menu buttons are visible.",
                reply_markup=self._main_reply_keyboard(),
            )
            return
        if action == "hide_menu":
            self._set_menu_visible(chat_id, False)
            await self._send_text(
                chat_id,
                "Menu buttons hidden.",
                reply_markup=self._hide_reply_keyboard(),
            )
            await self._send_text(
                chat_id,
                "Tap to restore menu:",
                reply_markup=self._make_inline_markup(
                    chat_id=chat_id,
                    rows=[[("📌 Show menu", "show_menu", None)]],
                ),
            )
            return
        if action == "show_status":
            await self._send_status(chat_id)
            return
        if action == "show_sessions":
            await self._send_sessions(chat_id)
            return
        if action == "show_projects":
            self._pending_new_project.pop(chat_id, None)
            self._pending_new_repo.pop(chat_id, None)
            self._pending_bootstrap.pop(chat_id, None)
            await self._send_projects(chat_id)
            return
        if action == "new_project_start":
            self._pending_new_project[chat_id] = {"expires_at": time.time() + 900}
            await self._send_text(
                chat_id,
                "Send the new project name in your next message.\n"
                "Tip: use a short stable name, e.g. `payments-core`.\n"
                "Use /projects to cancel this and return to project list.",
            )
            return
        if action == "confirm_newrepo":
            await self._clear_inline_markup_from_callback(callback)
            await self._send_text(chat_id, "✅ Selected: create repository")
            await self._confirm_new_repository(chat_id)
            return
        if action == "cancel_newrepo":
            await self._clear_inline_markup_from_callback(callback)
            self._pending_new_repo.pop(chat_id, None)
            await self._send_text(chat_id, "Repository plan cancelled.")
            return
        if action == "confirm_bootstrap":
            await self._clear_inline_markup_from_callback(callback)
            await self._send_text(chat_id, "✅ Selected: run bootstrap flow")
            await self._execute_bootstrap_flow(chat_id)
            return
        if action == "cancel_bootstrap":
            await self._clear_inline_markup_from_callback(callback)
            self._pending_bootstrap.pop(chat_id, None)
            await self._send_text(chat_id, "Bootstrap plan cancelled.")
            return
        if action == "select_project":
            pid = str(payload.get("project_id") or "")
            if not pid or self._manager.get_project(pid) is None:
                await self._send_text(chat_id, "Project not found.")
                return
            self._set_project_for_chat(chat_id, pid)
            sid = await self._ensure_session_for_project(pid)
            self._bind_chat(chat_id, sid)
            self._clear_pending_input_state(chat_id, sid)
            await self._send_text(chat_id, f"Active project set to: {pid}")
            await self._send_status(chat_id)
            return
        if action == "new_session":
            s = await self._manager.create_session(project_id=self._selected_project_id(chat_id))
            self._bind_chat(chat_id, s.id)
            self._clear_pending_input_state(chat_id, s.id)
            await self._send_text(chat_id, f"Created and bound new session: {s.id}")
            await self._send_status(chat_id)
            return
        if action == "bind_session":
            sid = str(payload.get("session_id") or "")
            if not sid or self._manager.get_session(sid) is None:
                await self._send_text(chat_id, "Session not found (maybe expired).")
                return
            self._bind_chat(chat_id, sid)
            self._clear_pending_input_state(chat_id, sid)
            await self._send_text(chat_id, f"Bound to session: {sid}")
            await self._send_status(chat_id)
            return
        if action == "run_worker":
            await self._run_worker_default(chat_id)
            return
        if action == "stop_worker":
            await self._stop_worker(chat_id)
            return
        if action == "cancel_turn":
            await self._cancel_queen_turn(chat_id)
            return
        if action == "show_retention":
            await self._send_retention_status(chat_id)
            return
        if action == "show_digest":
            await self._send_retention_digest(chat_id, proactive=False)
            return
        if action == "show_autodigest":
            await self._send_autonomous_digest(chat_id, proactive=False)
            return
        if action == "show_toolchain":
            await self._send_toolchain_status(chat_id)
            return
        if action == "plan_toolchain":
            workspace_path = str(payload.get("workspace_path") or "").strip() or None
            repository = str(payload.get("repository") or "").strip() or None
            await self._plan_project_toolchain(
                chat_id,
                workspace_path=workspace_path,
                repository=repository,
            )
            return
        if action == "approve_toolchain":
            token = str(payload.get("token") or "").strip() or None
            await self._approve_project_toolchain(chat_id, confirm_token=token)
            return
        if action == "send_choice":
            await self._clear_inline_markup_from_callback(callback)
            choice_text = str(payload.get("text") or "").strip()
            if choice_text:
                self._pending_choice.pop(chat_id, None)
                session_id = self._chat_session.get(chat_id)
                if session_id:
                    self._last_input_sig.pop((chat_id, session_id), None)
                await self._send_text(chat_id, f"✅ Selected: {choice_text}")
                await self._inject_user_input(chat_id, choice_text)
            return
        if action == "question_answer":
            await self._clear_inline_markup_from_callback(callback)
            answer = str(payload.get("answer") or "").strip()
            await self._advance_questionnaire(chat_id, answer, selected_via_button=True)
            return
        if action == "question_cancel":
            await self._clear_inline_markup_from_callback(callback)
            self._pending_questions.pop(chat_id, None)
            await self._send_text(chat_id, "Questionnaire cancelled. You can type a free-form response.")
            return

    async def _advance_questionnaire(
        self,
        chat_id: str,
        answer: str,
        *,
        selected_via_button: bool = False,
    ) -> None:
        state = self._pending_questions.get(chat_id)
        if not state:
            await self._send_text(chat_id, "No active questionnaire. Send text normally.")
            return
        questions = state.get("questions") or []
        idx = int(state.get("index", 0))
        if idx >= len(questions):
            self._pending_questions.pop(chat_id, None)
            return

        q = questions[idx]
        answers = state.setdefault("answers", [])
        answers.append({"id": q.get("id"), "prompt": q.get("prompt"), "answer": answer})
        state["index"] = idx + 1
        state["expires_at"] = time.time() + 1800

        if selected_via_button:
            await self._send_text(chat_id, f"✅ Selected: {answer}")

        if state["index"] >= len(questions):
            session_id = str(state.get("session_id") or "")
            lines = ["Answers:"]
            for item in answers:
                prompt = str(item.get("prompt") or item.get("id") or "question").strip()
                lines.append(f"- {prompt}: {item.get('answer', '')}")
            self._pending_questions.pop(chat_id, None)
            self._last_input_sig.pop((chat_id, session_id), None)
            await self._inject_user_input(chat_id, "\n".join(lines))
            return

        await self._send_next_question(chat_id)

    async def _send_next_question(self, chat_id: str) -> None:
        state = self._pending_questions.get(chat_id)
        if not state:
            return
        questions = state.get("questions") or []
        idx = int(state.get("index", 0))
        if idx >= len(questions):
            return
        q = questions[idx]
        prompt = str(q.get("prompt") or q.get("id") or "Question").strip()
        opts = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        total = len(questions)
        text = f"Question {idx + 1}/{total}\n{prompt}"

        rows: list[list[tuple[str, str, dict[str, Any] | None]]] = []
        if opts:
            for opt in opts[:8]:
                rows.append([(opt, "question_answer", {"answer": opt})])
        rows.append([("✍️ Type custom answer", "show_help", None), ("🚫 Cancel", "question_cancel", None)])
        await self._send_text(
            chat_id,
            text,
            reply_markup=self._make_inline_markup(chat_id=chat_id, rows=rows),
        )

    async def _offer_input_request(
        self,
        chat_id: str,
        *,
        session_id: str,
        prompt: str,
        options: list[str],
        questions: list[dict[str, Any]],
    ) -> None:
        sig = f"{prompt}|{options}|{[(q.get('id'), q.get('prompt')) for q in questions]}"
        key = (chat_id, session_id)
        if self._last_input_sig.get(key) == sig:
            return
        self._last_input_sig[key] = sig

        if questions:
            self._pending_choice.pop(chat_id, None)
            self._pending_questions[chat_id] = {
                "session_id": session_id,
                "questions": questions,
                "index": 0,
                "answers": [],
                "expires_at": time.time() + 1800,
            }
            header = "Please answer a short questionnaire:"
            if prompt:
                header = f"{header}\n{prompt}"
            await self._send_text(chat_id, header)
            await self._send_next_question(chat_id)
            return

        if options:
            self._pending_questions.pop(chat_id, None)
            self._pending_choice[chat_id] = {
                "session_id": session_id,
                "options": options,
                "prompt": prompt,
                "expires_at": time.time() + 1800,
            }
            rows = [[(opt, "send_choice", {"text": opt})] for opt in options[:8]]
            rows.append([("✍️ Type custom answer", "show_help", None)])
            await self._send_text(
                chat_id,
                prompt or "Choose one option:",
                reply_markup=self._make_inline_markup(chat_id=chat_id, rows=rows),
            )
            return

        if prompt:
            await self._send_text(chat_id, f"Input requested:\n{prompt}")

    async def _handle_text_update(self, chat_id: str, text: str) -> None:
        if await self._handle_command(chat_id, text):
            return

        pending_project = self._pending_new_project.get(chat_id)
        if pending_project:
            name = text.strip()
            if not name:
                await self._send_text(chat_id, "Project name cannot be empty. Send another name.")
                return
            created = self._manager.create_project(name=name)
            pid = str(created.get("id") or "")
            self._set_project_for_chat(chat_id, pid)
            sid = await self._ensure_session_for_project(pid)
            self._bind_chat(chat_id, sid)
            self._clear_pending_input_state(chat_id, sid)
            await self._send_text(chat_id, f"Created project '{created.get('name')}' ({pid})")
            await self._send_status(chat_id)
            return
        if chat_id in self._pending_new_repo:
            await self._send_text(
                chat_id,
                "There is a pending repository plan. Tap confirm/cancel or run /newrepo again.",
            )
            return
        if chat_id in self._pending_bootstrap:
            await self._send_text(
                chat_id,
                "There is a pending bootstrap plan. Tap confirm/cancel or run /bootstrap again.",
            )
            return

        if chat_id in self._pending_questions:
            await self._advance_questionnaire(chat_id, text)
            return

        pending = self._pending_choice.get(chat_id)
        if pending:
            options = [str(o) for o in pending.get("options", [])]
            if text in options:
                self._pending_choice.pop(chat_id, None)
                session_id = self._chat_session.get(chat_id)
                if session_id:
                    self._last_input_sig.pop((chat_id, session_id), None)
                await self._inject_user_input(chat_id, text)
                return

        await self._inject_user_input(chat_id, text)

    async def _handle_update(self, update: dict[str, Any]) -> None:
        self._prune_state()

        callback = update.get("callback_query")
        if isinstance(callback, dict):
            await self._handle_callback_query(callback)
            return

        msg = update.get("message") or update.get("edited_message")
        if not isinstance(msg, dict):
            return

        from_user = msg.get("from") or {}
        if from_user.get("is_bot"):
            return

        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        text = (msg.get("text") or "").strip()
        if chat_id is None or not text:
            return

        chat_id_str = str(chat_id)
        self._remember_chat(chat_id_str)
        logger.info("Telegram bridge received chat=%s text_len=%d", chat_id_str, len(text))
        await self._handle_text_update(chat_id_str, text)

    async def _poll_loop(self) -> None:
        backoff = 1.0
        while not self._stopped.is_set():
            try:
                payload = {
                    "timeout": 25,
                    "offset": self._offset,
                    "allowed_updates": ["message", "edited_message", "callback_query"],
                }
                data = await self._api("getUpdates", payload)
                for upd in data.get("result", []):
                    uid = int(upd.get("update_id", 0))
                    if uid >= self._offset:
                        self._offset = uid + 1
                    await self._handle_update(upd)
                backoff = 1.0
                self._last_poll_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                detail = self._format_exception_details(exc)
                self._last_poll_error = detail
                logger.warning("Telegram bridge polling error: %s", detail)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 20.0)

    def _try_acquire_poll_lock(self) -> bool:
        lock_dir = os.path.dirname(self._poll_lock_path)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)
        fh = open(self._poll_lock_path, "a+", encoding="utf-8")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            fh.close()
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                logger.warning(
                    "Telegram bridge lock already held at %s; skip polling startup",
                    self._poll_lock_path,
                )
                self._poller_owner = False
                return False
            raise
        self._poll_lock_file = fh
        self._poller_owner = True
        logger.info("Telegram bridge acquired poll lock: %s", self._poll_lock_path)
        return True

    def _release_poll_lock(self) -> None:
        fh = self._poll_lock_file
        self._poll_lock_file = None
        if fh is None:
            self._poller_owner = False
            return
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            logger.exception("Telegram bridge failed to release poll lock")
        try:
            fh.close()
        except Exception:
            logger.exception("Telegram bridge failed to close poll lock file")
        self._poller_owner = False

    def status(self) -> dict[str, Any]:
        poll_task = self._poll_task
        poll_running = bool(poll_task is not None and not poll_task.done())
        return {
            "enabled": self._enabled,
            "mode": self._mode,
            "single_consumer": self._single_consumer,
            "poll_lock_path": self._poll_lock_path,
            "poller_owner": self._poller_owner,
            "running": poll_running,
            "startup_status": self._startup_status,
            "last_poll_error": self._last_poll_error,
        }

    async def _on_client_output_delta(self, session_id: str, event: Any) -> None:
        if event.stream_id != "queen":
            return
        snapshot = str((event.data or {}).get("snapshot", "")).strip()
        if snapshot:
            self._latest_snapshot[session_id] = snapshot

    async def _broadcast_snapshot(self, session_id: str) -> None:
        snapshot = self._latest_snapshot.get(session_id, "").strip()
        if not snapshot:
            return

        chats = self._chats_for_session(session_id)
        for chat_id in chats:
            key = (chat_id, session_id)
            if self._last_sent.get(key) == snapshot:
                continue
            await self._send_text(chat_id, snapshot)
            self._last_sent[key] = snapshot

    async def _on_turn_boundary(self, session_id: str, event: Any) -> None:
        if event.stream_id != "queen":
            return
        await self._broadcast_snapshot(session_id)

    async def _on_client_input_requested(self, session_id: str, event: Any) -> None:
        if event.stream_id != "queen":
            return
        await self._broadcast_snapshot(session_id)

        data = dict(event.data or {})
        prompt = str(data.get("prompt") or "").strip()
        options = [str(o).strip() for o in (data.get("options") or []) if str(o).strip()]

        raw_questions = data.get("questions") or []
        questions: list[dict[str, Any]] = []
        if isinstance(raw_questions, list):
            for q in raw_questions:
                if not isinstance(q, dict):
                    continue
                q_opts = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
                questions.append(
                    {
                        "id": str(q.get("id") or "").strip(),
                        "prompt": str(q.get("prompt") or "").strip(),
                        "options": q_opts,
                    }
                )

        chats = self._chats_for_session(session_id)
        for chat_id in chats:
            await self._offer_input_request(
                chat_id,
                session_id=session_id,
                prompt=prompt,
                options=options,
                questions=questions,
            )

    async def _on_client_input_received(self, session_id: str, event: Any) -> None:
        """Mirror user inputs across interfaces for a shared session timeline.

        - Web-originated input is echoed to all Telegram chats bound to the session.
        - Telegram-originated input is echoed only to other bound Telegram chats
          (the source chat already has the original user message from Telegram itself).
        """
        if event.stream_id != "queen":
            return
        data = dict(event.data or {})
        content = str(data.get("content") or "").strip()
        if not content:
            return
        source = str(data.get("source") or "").strip().lower()
        source_chat_id = str(data.get("chat_id") or "").strip()

        chats = self._chats_for_session(session_id)
        if not chats:
            return

        if source == "web":
            prefix = "🌐 Web user"
        elif source == "telegram":
            prefix = "💬 Telegram user"
        else:
            prefix = "👤 User"
        mirrored = f"{prefix}: {content}"

        for chat_id in chats:
            if source == "telegram" and source_chat_id and chat_id == source_chat_id:
                continue
            await self._send_text(chat_id, mirrored)

    async def _subscribe_session(self, session: Any) -> None:
        sid = session.id
        if sid in self._subs:
            return

        bus = session.event_bus

        async def _on_delta(event: Any) -> None:
            await self._on_client_output_delta(sid, event)

        async def _on_turn(event: Any) -> None:
            await self._on_turn_boundary(sid, event)

        async def _on_request(event: Any) -> None:
            await self._on_client_input_requested(sid, event)

        async def _on_input(event: Any) -> None:
            await self._on_client_input_received(sid, event)

        sub_ids = [
            bus.subscribe(event_types=[EventType.CLIENT_OUTPUT_DELTA], handler=_on_delta),
            bus.subscribe(event_types=[EventType.LLM_TURN_COMPLETE], handler=_on_turn),
            bus.subscribe(event_types=[EventType.CLIENT_INPUT_REQUESTED], handler=_on_request),
            bus.subscribe(event_types=[EventType.CLIENT_INPUT_RECEIVED], handler=_on_input),
        ]
        self._subs[sid] = sub_ids

    async def _unsubscribe_session(self, session_id: str) -> None:
        session = self._manager.get_session(session_id)
        sub_ids = self._subs.pop(session_id, [])
        if session is not None:
            for sub_id in sub_ids:
                try:
                    session.event_bus.unsubscribe(sub_id)
                except Exception:
                    pass
        self._session_chats.pop(session_id, None)

    async def _unsubscribe_all(self) -> None:
        for sid in list(self._subs.keys()):
            await self._unsubscribe_session(sid)
        self._subs.clear()

    async def _sync_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                live_ids = {s.id for s in self._manager.list_sessions()}
                for s in self._manager.list_sessions():
                    await self._subscribe_session(s)
                for sid in list(self._subs.keys()):
                    if sid not in live_ids:
                        await self._unsubscribe_session(sid)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram bridge sync loop failed")
            await asyncio.sleep(2.0)

    async def _retention_digest_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                now = time.localtime()
                time_key = f"{now.tm_year:04d}-{now.tm_mon:02d}-{now.tm_mday:02d}"
                if now.tm_hour == self._retention_digest_hour and now.tm_min == self._retention_digest_minute:
                    for chat_id in list(self._known_chats):
                        if self._retention_last_sent_key.get(chat_id) == time_key:
                            continue
                        sent = await self._send_retention_digest(chat_id, proactive=True)
                        if sent:
                            self._retention_last_sent_key[chat_id] = time_key
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram bridge retention digest loop failed")
            await asyncio.sleep(30.0)

    async def _autonomous_digest_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                now = time.localtime()
                time_key = f"{now.tm_year:04d}-{now.tm_mon:02d}-{now.tm_mday:02d}"
                if now.tm_hour == self._autonomous_digest_hour and now.tm_min == self._autonomous_digest_minute:
                    for chat_id in list(self._known_chats):
                        if self._autonomous_last_sent_key.get(chat_id) == time_key:
                            continue
                        sent = await self._send_autonomous_digest(chat_id, proactive=True)
                        if sent:
                            self._autonomous_last_sent_key[chat_id] = time_key
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram bridge autonomous digest loop failed")
            await asyncio.sleep(30.0)

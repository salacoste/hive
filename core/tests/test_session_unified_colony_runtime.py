"""SessionManager runtime wiring tests for the current worker contract.

The legacy `_start_unified_colony_runtime` helper is no longer part of the
SessionManager lifecycle. Current wiring loads workers via `_load_worker_core`
into `session.graph_runtime`, then teardown goes through `unload_graph` and
`stop_session`.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from framework.runtime.event_bus import EventBus
from framework.server.session_manager import Session, SessionManager


def _make_session(session_id: str) -> Session:
    return Session(id=session_id, event_bus=EventBus(), llm=object(), loaded_at=0.0)


def _make_runner_with_setup_bridge() -> tuple[SimpleNamespace, SimpleNamespace, MagicMock]:
    runtime = SimpleNamespace(
        is_running=False,
        start=AsyncMock(),
        event_bus=None,
    )

    async def _start_runtime() -> None:
        runtime.is_running = True

    runtime.start.side_effect = _start_runtime

    def _setup_impl(*, event_bus) -> None:
        runtime.event_bus = event_bus
        runner._agent_runtime = runtime

    setup_mock = MagicMock(side_effect=_setup_impl)
    runner = SimpleNamespace(
        _llm=None,
        _agent_runtime=None,
        _setup=setup_mock,
        info=MagicMock(return_value={"id": "worker"}),
        cleanup_async=AsyncMock(),
    )
    return runner, runtime, setup_mock


@pytest.mark.asyncio
async def test_load_worker_core_bootstraps_runtime_and_starts_it(monkeypatch, tmp_path: Path) -> None:
    manager = SessionManager()
    session = _make_session("session_runtime_boot")
    runner, runtime, setup_mock = _make_runner_with_setup_bridge()

    monkeypatch.setattr("framework.runner.AgentRunner.load", lambda *_args, **_kwargs: runner)
    monkeypatch.setattr(manager, "_cleanup_stale_active_sessions", lambda *_args: None)
    monkeypatch.setattr(manager, "_subscribe_worker_colony_memory", AsyncMock())
    monkeypatch.setattr(
        "framework.tools.queen_lifecycle_tools._read_agent_triggers_json",
        lambda *_args: [],
    )

    await manager._load_worker_core(
        session,
        tmp_path / "worker_agent",
        graph_id="worker_graph",
    )

    assert setup_mock.call_count == 1
    runtime.start.assert_awaited_once()
    assert runtime.is_running is True
    assert runtime.event_bus is session.event_bus
    assert session.graph_id == "worker_graph"
    assert session.worker_path == tmp_path / "worker_agent"
    assert session.runner is runner
    assert session.graph_runtime is runtime
    assert session.worker_info == {"id": "worker"}


@pytest.mark.asyncio
async def test_unload_graph_cleans_runtime_and_worker_fields(monkeypatch, tmp_path: Path) -> None:
    manager = SessionManager()
    session = _make_session("session_unload_graph")
    runner, runtime, _setup_mock = _make_runner_with_setup_bridge()

    monkeypatch.setattr("framework.runner.AgentRunner.load", lambda *_args, **_kwargs: runner)
    monkeypatch.setattr(manager, "_cleanup_stale_active_sessions", lambda *_args: None)
    monkeypatch.setattr(manager, "_subscribe_worker_colony_memory", AsyncMock())
    monkeypatch.setattr(manager, "_notify_queen_worker_unloaded", AsyncMock())
    monkeypatch.setattr(
        "framework.tools.queen_lifecycle_tools._read_agent_triggers_json",
        lambda *_args: [],
    )

    await manager._load_worker_core(session, tmp_path / "worker_agent", graph_id="worker_graph")
    manager._sessions[session.id] = session

    unloaded = await manager.unload_graph(session.id)

    assert unloaded is True
    runner.cleanup_async.assert_awaited_once()
    manager._notify_queen_worker_unloaded.assert_awaited_once_with(session)
    assert session.graph_id is None
    assert session.worker_path is None
    assert session.runner is None
    assert session.graph_runtime is None
    assert session.worker_info is None


@pytest.mark.asyncio
async def test_stop_session_removes_session_and_cleans_runner() -> None:
    manager = SessionManager()
    session = _make_session("session_stop_cleanup")
    cleanup_async = AsyncMock()
    session.runner = SimpleNamespace(cleanup_async=cleanup_async)
    close_session_log = MagicMock()
    session.event_bus.close_session_log = close_session_log
    manager._sessions[session.id] = session

    stopped = await manager.stop_session(session.id)

    assert stopped is True
    assert session.id not in manager._sessions
    cleanup_async.assert_awaited_once()
    close_session_log.assert_called_once()

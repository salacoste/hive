"""
Comprehensive tests for the Hive HTTP API server.

Uses aiohttp TestClient with mocked sessions to test all endpoints
without requiring actual LLM calls or agent loading.
"""

import asyncio
import io
import json
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from framework.runtime.triggers import TriggerDefinition
from framework.server import routes_sessions
from framework.server.app import APP_KEY_CREDENTIAL_STORE, APP_KEY_MANAGER, create_app
from framework.server.routes_autonomous import APP_KEY_AUTONOMOUS_STORE
from framework.server.session_manager import Session, SessionManager

REPO_ROOT = Path(__file__).resolve().parents[4]
EXAMPLE_AGENT_PATH = REPO_ROOT / "examples" / "templates" / "deep_research_agent"

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


@dataclass
class MockNodeSpec:
    id: str
    name: str
    description: str = "A test node"
    node_type: str = "event_loop"
    input_keys: list = field(default_factory=list)
    output_keys: list = field(default_factory=list)
    nullable_output_keys: list = field(default_factory=list)
    tools: list = field(default_factory=list)
    routes: dict = field(default_factory=dict)
    max_retries: int = 3
    max_node_visits: int = 0
    client_facing: bool = False
    success_criteria: str | None = None
    system_prompt: str | None = None
    sub_agents: list = field(default_factory=list)


@dataclass
class MockEdgeSpec:
    id: str
    source: str
    target: str
    condition: str = "on_success"
    priority: int = 0


@dataclass
class MockGraphSpec:
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    entry_node: str = ""

    def get_node(self, node_id: str):
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None


@dataclass
class MockEntryPoint:
    id: str = "default"
    name: str = "Default"
    entry_node: str = "start"
    trigger_type: str = "manual"
    trigger_config: dict = field(default_factory=dict)


@dataclass
class MockStream:
    is_awaiting_input: bool = False
    _execution_tasks: dict = field(default_factory=dict)
    _active_executors: dict = field(default_factory=dict)
    active_execution_ids: set = field(default_factory=set)

    async def cancel_execution(self, execution_id: str, reason: str | None = None) -> bool:
        return execution_id in self._execution_tasks


@dataclass
class MockGraphRegistration:
    graph: MockGraphSpec = field(default_factory=MockGraphSpec)
    streams: dict = field(default_factory=dict)
    entry_points: dict = field(default_factory=dict)


class MockRuntime:
    """Minimal mock of AgentRuntime with the methods used by route handlers."""

    def __init__(self, graph=None, entry_points=None, log_store=None):
        self._graph = graph or MockGraphSpec()
        self._entry_points = entry_points or [MockEntryPoint()]
        self._runtime_log_store = log_store
        self._mock_streams = {"default": MockStream()}
        self._registration = MockGraphRegistration(
            graph=self._graph,
            streams=self._mock_streams,
            entry_points={"default": self._entry_points[0]},
        )

    def list_graphs(self):
        return ["primary"]

    def get_graph_registration(self, graph_id):
        if graph_id == "primary":
            return self._registration
        return None

    def get_entry_points(self):
        return self._entry_points

    async def trigger(self, ep_id, input_data=None, session_state=None):
        return "exec_test_123"

    async def inject_input(self, node_id, content, graph_id=None, *, is_client_input=False):
        return True

    def pause_timers(self):
        pass

    async def get_goal_progress(self):
        return {"progress": 0.5, "criteria": []}

    def find_awaiting_node(self):
        return None, None

    def get_stats(self):
        return {"running": True, "executions": 1}

    def get_timer_next_fire_in(self, ep_id):
        return None


class MockAgentInfo:
    name: str = "test_agent"
    description: str = "A test agent"
    goal_name: str = "test_goal"
    node_count: int = 2


def _make_queen_executor():
    """Create a mock queen executor with an injectable queen node."""
    mock_node = MagicMock()
    mock_node.inject_event = AsyncMock()
    executor = MagicMock()
    executor.node_registry = {"queen": mock_node}
    return executor


def _make_session(
    agent_id="test_agent",
    tmp_dir=None,
    runtime=None,
    nodes=None,
    edges=None,
    log_store=None,
    with_queen=True,
):
    """Create a mock Session backed by a temp directory."""
    agent_path = Path(tmp_dir) if tmp_dir else Path("/tmp/test_agent")
    graph = MockGraphSpec(nodes=nodes or [], edges=edges or [])
    rt = runtime or MockRuntime(graph=graph, log_store=log_store)
    runner = MagicMock()
    runner.cleanup = AsyncMock()
    runner.intro_message = "Test intro"

    mock_event_bus = MagicMock()
    mock_event_bus.publish = AsyncMock()
    mock_llm = MagicMock()

    queen_executor = _make_queen_executor() if with_queen else None

    return Session(
        id=agent_id,
        event_bus=mock_event_bus,
        llm=mock_llm,
        loaded_at=1000000.0,
        queen_executor=queen_executor,
        graph_id=agent_id,
        worker_path=agent_path,
        runner=runner,
        graph_runtime=rt,
        worker_info=MockAgentInfo(),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def tmp_agent_dir(tmp_path, monkeypatch):
    """Create a temporary agent directory with session/checkpoint/conversation data.

    Monkeypatches Path.home() so that route handlers resolve session paths
    to the temp directory instead of the real home.
    """
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    agent_name = "test_agent"
    base = tmp_path / ".hive" / "agents" / agent_name
    sessions_dir = base / "sessions"
    sessions_dir.mkdir(parents=True)
    return tmp_path, agent_name, base


def _write_sample_session(base: Path, session_id: str):
    """Create a sample worker session on disk."""
    session_dir = base / "sessions" / session_id

    # state.json
    session_dir.mkdir(parents=True)
    state = {
        "status": "paused",
        "started_at": "2026-02-20T12:00:00",
        "completed_at": None,
        "input_data": {"user_request": "test input"},
        "data_buffer": {"key1": "value1"},
        "progress": {
            "current_node": "node_b",
            "paused_at": "node_b",
            "steps_executed": 5,
            "path": ["node_a", "node_b"],
            "node_visit_counts": {"node_a": 1, "node_b": 1},
            "nodes_with_failures": ["node_b"],
        },
    }
    (session_dir / "state.json").write_text(json.dumps(state))

    # Checkpoints
    cp_dir = session_dir / "checkpoints"
    cp_dir.mkdir()
    cp_data = {
        "checkpoint_id": "cp_node_complete_node_a_001",
        "current_node": "node_a",
        "next_node": "node_b",
        "is_clean": True,
        "timestamp": "2026-02-20T12:01:00",
    }
    (cp_dir / "cp_node_complete_node_a_001.json").write_text(json.dumps(cp_data))

    # Conversations
    conv_dir = session_dir / "conversations" / "node_a" / "parts"
    conv_dir.mkdir(parents=True)
    (conv_dir / "0001.json").write_text(json.dumps({"seq": 1, "role": "user", "content": "hello"}))
    (conv_dir / "0002.json").write_text(
        json.dumps({"seq": 2, "role": "assistant", "content": "hi there"})
    )

    conv_dir_b = session_dir / "conversations" / "node_b" / "parts"
    conv_dir_b.mkdir(parents=True)
    (conv_dir_b / "0003.json").write_text(
        json.dumps({"seq": 3, "role": "user", "content": "continue"})
    )

    # Logs
    logs_dir = session_dir / "logs"
    logs_dir.mkdir()
    summary = {
        "run_id": session_id,
        "status": "paused",
        "total_nodes_executed": 2,
        "node_path": ["node_a", "node_b"],
    }
    (logs_dir / "summary.json").write_text(json.dumps(summary))

    detail_a = {"node_id": "node_a", "node_name": "Node A", "success": True, "total_steps": 3}
    detail_b = {
        "node_id": "node_b",
        "node_name": "Node B",
        "success": False,
        "error": "timeout",
        "retry_count": 2,
        "needs_attention": True,
        "attention_reasons": ["retried"],
        "total_steps": 1,
    }
    (logs_dir / "details.jsonl").write_text(
        json.dumps(detail_a) + "\n" + json.dumps(detail_b) + "\n"
    )

    step_a = {"node_id": "node_a", "step_index": 0, "llm_text": "thinking..."}
    step_b = {"node_id": "node_b", "step_index": 0, "llm_text": "retrying..."}
    (logs_dir / "tool_logs.jsonl").write_text(json.dumps(step_a) + "\n" + json.dumps(step_b) + "\n")

    return session_id, session_dir, state


@pytest.fixture
def sample_session(tmp_agent_dir):
    """Create a sample session with state.json, checkpoints, and conversations."""
    _tmp_path, _agent_name, base = tmp_agent_dir
    return _write_sample_session(base, "session_20260220_120000_abc12345")


@pytest.fixture
def custom_id_session(tmp_agent_dir):
    """Create a sample session that uses a custom non-session_* ID."""
    _tmp_path, _agent_name, base = tmp_agent_dir
    return _write_sample_session(base, "my-custom-session")


def _make_app_with_session(session):
    """Create an aiohttp app with a pre-loaded session."""
    app = create_app()
    mgr = app[APP_KEY_MANAGER]
    mgr._sessions[session.id] = session
    return app


@pytest.fixture
def nodes_and_edges():
    """Standard test nodes and edges."""
    nodes = [
        MockNodeSpec(
            id="node_a",
            name="Node A",
            description="First node",
            input_keys=["user_request"],
            output_keys=["result"],
            success_criteria="Produce a valid result",
            system_prompt="You are a helpful assistant that produces valid results.",
        ),
        MockNodeSpec(
            id="node_b",
            name="Node B",
            description="Second node",
            input_keys=["result"],
            output_keys=["final_output"],
            client_facing=True,
        ),
    ]
    edges = [
        MockEdgeSpec(id="e1", source="node_a", target="node_b", condition="on_success"),
    ]
    return nodes, edges


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestHealth:
    @pytest.mark.asyncio
    async def test_health(self):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/health")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
            assert data["agents_loaded"] == 0
            assert data["sessions"] == 0

    @pytest.mark.asyncio
    async def test_telegram_bridge_status_endpoint(self):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/telegram/bridge/status")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] in {"ok", "disabled"}
            assert isinstance(data.get("bridge"), dict)


class TestSessionCRUD:
    @pytest.mark.asyncio
    async def test_create_session_with_worker_forwards_session_id(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        manager.create_session_with_worker_graph = AsyncMock(
            return_value=_make_session(agent_id="my-custom-session")
        )

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions",
                json={
                    "session_id": "my-custom-session",
                    "agent_path": str(EXAMPLE_AGENT_PATH),
                    "project_id": "proj-1",
                },
            )
            data = await resp.json()

        assert resp.status == 201
        assert data["session_id"] == "my-custom-session"
        manager.create_session_with_worker_graph.assert_awaited_once_with(
            str(EXAMPLE_AGENT_PATH.resolve()),
            agent_id=None,
            session_id="my-custom-session",
            model=None,
            model_profile=None,
            initial_prompt=None,
            queen_resume_from=None,
            project_id="proj-1",
        )

    @pytest.mark.asyncio
    async def test_create_session_queen_only_forwards_project_id(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        manager.create_session = AsyncMock(return_value=_make_session(agent_id="queen-only-session"))

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions",
                json={
                    "session_id": "queen-only-session",
                    "project_id": "proj-queen",
                    "initial_prompt": "hello",
                },
            )
            data = await resp.json()

        assert resp.status == 201
        assert data["session_id"] == "queen-only-session"
        manager.create_session.assert_awaited_once_with(
            session_id="queen-only-session",
            model=None,
            model_profile=None,
            initial_prompt="hello",
            queen_resume_from=None,
            project_id="proj-queen",
        )

    @pytest.mark.asyncio
    async def test_create_session_project_not_found_returns_project_hint(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions",
                json={
                    "project_id": "missing-project-id",
                    "initial_prompt": "hello",
                },
            )
            assert resp.status == 409
            data = await resp.json()

        assert data["error"] == "Project 'missing-project-id' not found"
        assert "Use an existing project_id" in data["hint"]
        assert data["default_project_id"] == manager.default_project_id()
        assert manager.default_project_id() in data["available_project_ids"]

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions")
            assert resp.status == 200
            data = await resp.json()
            assert data["sessions"] == []

    @pytest.mark.asyncio
    async def test_list_sessions_with_loaded(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions")
            assert resp.status == 200
            data = await resp.json()
            assert len(data["sessions"]) == 1
            assert data["sessions"][0]["session_id"] == "test_agent"
            assert data["sessions"][0]["intro_message"] == "Test intro"

    @pytest.mark.asyncio
    async def test_list_sessions_filters_by_project_id(self):
        s1 = _make_session(agent_id="session_p1")
        s1.project_id = "project-1"
        s2 = _make_session(agent_id="session_p2")
        s2.project_id = "project-2"
        app = _make_app_with_session(s1)
        app[APP_KEY_MANAGER]._sessions[s2.id] = s2

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions?project_id=project-1")
            assert resp.status == 200
            data = await resp.json()

        assert [s["session_id"] for s in data["sessions"]] == ["session_p1"]
        assert data["sessions"][0]["project_id"] == "project-1"

    @pytest.mark.asyncio
    async def test_session_history_filters_by_project_id_and_respects_live_project(
        self, monkeypatch
    ):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        live = _make_session(agent_id="live_session")
        live.project_id = "project-live"
        manager._sessions[live.id] = live

        monkeypatch.setattr(
            SessionManager,
            "list_cold_sessions",
            staticmethod(
                lambda: [
                    {
                        "session_id": "live_session",
                        "cold": True,
                        "live": False,
                        "has_messages": True,
                        "created_at": 100.0,
                        "agent_name": None,
                        "agent_path": None,
                        "project_id": None,
                    },
                    {
                        "session_id": "cold_other_project",
                        "cold": True,
                        "live": False,
                        "has_messages": True,
                        "created_at": 90.0,
                        "agent_name": "Other",
                        "agent_path": "/tmp/other",
                        "project_id": "project-other",
                    },
                ]
            ),
        )

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/history?project_id=project-live")
            assert resp.status == 200
            data = await resp.json()

        assert len(data["sessions"]) == 1
        only = data["sessions"][0]
        assert only["session_id"] == "live_session"
        assert only["project_id"] == "project-live"
        assert only["live"] is True
        assert only["cold"] is False

    @pytest.mark.asyncio
    async def test_get_session_found(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent")
            assert resp.status == 200
            data = await resp.json()
            assert data["session_id"] == "test_agent"
            assert data["has_worker"] is True
            assert "entry_points" in data
            assert "graphs" in data

    @pytest.mark.asyncio
    async def test_get_session_not_found(self):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/nonexistent")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_stop_session(self):
        session = _make_session()
        session.runner.cleanup_async = AsyncMock()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/sessions/test_agent")
            assert resp.status == 200
            data = await resp.json()
            assert data["stopped"] is True

            # Verify it's gone
            resp2 = await client.get("/api/sessions/test_agent")
            assert resp2.status == 404

    @pytest.mark.asyncio
    async def test_stop_session_not_found(self):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/sessions/nonexistent")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_reveal_session_folder_returns_fallback_when_launcher_fails(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        session = _make_session(agent_id="session_reveal_fail")
        app = _make_app_with_session(session)

        monkeypatch.setattr(
            routes_sessions.subprocess,
            "run",
            lambda *args, **kwargs: SimpleNamespace(
                returncode=1,
                stderr="no file manager available",
                stdout="",
            ),
        )

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(f"/api/sessions/{session.id}/reveal")
            assert resp.status == 200
            data = await resp.json()

        assert data["opened"] is False
        assert data["launcher"] in {"open", "explorer", "xdg-open"}
        assert "no file manager available" in data["error"]
        assert session.id in data["path"]

    @pytest.mark.asyncio
    async def test_reveal_session_folder_returns_container_hint_when_launcher_missing(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        session = _make_session(agent_id="session_reveal_missing_launcher")
        app = _make_app_with_session(session)

        def _raise_missing_launcher(*args, **kwargs):
            raise FileNotFoundError("xdg-open not found")

        monkeypatch.setattr(routes_sessions.subprocess, "run", _raise_missing_launcher)

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(f"/api/sessions/{session.id}/reveal")
            assert resp.status == 200
            data = await resp.json()

        assert data["opened"] is False
        assert data["launcher"] in {"open", "explorer", "xdg-open"}
        assert "unavailable in this environment" in data["error"]
        assert "Export" in (data.get("hint") or "")
        assert session.id in data["path"]

    @pytest.mark.asyncio
    async def test_reveal_session_folder_returns_opened_true_on_success(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        session = _make_session(agent_id="session_reveal_ok")
        app = _make_app_with_session(session)

        monkeypatch.setattr(
            routes_sessions.subprocess,
            "run",
            lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr="", stdout=""),
        )

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(f"/api/sessions/{session.id}/reveal")
            assert resp.status == 200
            data = await resp.json()

        assert data["opened"] is True
        assert data["launcher"] in {"open", "explorer", "xdg-open"}
        assert session.id in data["path"]

    @pytest.mark.asyncio
    async def test_export_session_folder_returns_zip_payload(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        session = _make_session(agent_id="session_export_ok")
        app = _make_app_with_session(session)

        session_dir = tmp_path / ".hive" / "queen" / "session" / session.id / "data"
        session_dir.mkdir(parents=True)
        (session_dir / "note.txt").write_text("hello-export", encoding="utf-8")

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(f"/api/sessions/{session.id}/export")
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "application/zip"
            assert "attachment;" in (resp.headers.get("Content-Disposition") or "")
            body = await resp.read()

        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            assert "data/note.txt" in archive.namelist()
            assert archive.read("data/note.txt").decode("utf-8") == "hello-export"

    @pytest.mark.asyncio
    async def test_export_session_folder_uses_resume_storage_id(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        session = _make_session(agent_id="session_live")
        session.queen_resume_from = "session_original"
        app = _make_app_with_session(session)

        session_dir = tmp_path / ".hive" / "queen" / "session" / "session_original" / "logs"
        session_dir.mkdir(parents=True)
        (session_dir / "summary.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/session_live/export")
            assert resp.status == 200
            body = await resp.read()

        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            assert "logs/summary.json" in archive.namelist()
            assert json.loads(archive.read("logs/summary.json").decode("utf-8")) == {"ok": True}

    @pytest.mark.asyncio
    async def test_export_session_folder_returns_404_when_folder_missing(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        session = _make_session(agent_id="session_export_missing")
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(f"/api/sessions/{session.id}/export")
            assert resp.status == 404
            data = await resp.json()

        assert "Session folder not found" in data["error"]

    @pytest.mark.asyncio
    async def test_session_stats(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/stats")
            assert resp.status == 200
            data = await resp.json()
            assert data["running"] is True

    @pytest.mark.asyncio
    async def test_session_entry_points(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/entry-points")
            assert resp.status == 200
            data = await resp.json()
            assert len(data["entry_points"]) == 1
            assert data["entry_points"][0]["id"] == "default"

    @pytest.mark.asyncio
    async def test_session_graphs(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/graphs")
            assert resp.status == 200
            data = await resp.json()
            assert "primary" in data["graphs"]

    @pytest.mark.asyncio
    async def test_update_trigger_task(self, tmp_path):
        session = _make_session(tmp_dir=tmp_path)
        session.available_triggers["daily"] = TriggerDefinition(
            id="daily",
            trigger_type="timer",
            trigger_config={"cron": "0 5 * * *"},
            task="Old task",
        )
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.patch(
                "/api/sessions/test_agent/triggers/daily",
                json={"task": "New task"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["task"] == "New task"
            assert data["trigger_config"]["cron"] == "0 5 * * *"
            assert session.available_triggers["daily"].task == "New task"

    @pytest.mark.asyncio
    async def test_update_trigger_cron_restarts_active_timer(self, tmp_path):
        session = _make_session(tmp_dir=tmp_path)
        session.available_triggers["daily"] = TriggerDefinition(
            id="daily",
            trigger_type="timer",
            trigger_config={"cron": "0 5 * * *"},
            task="Run task",
            active=True,
        )
        session.active_trigger_ids.add("daily")
        session.active_timer_tasks["daily"] = asyncio.create_task(asyncio.sleep(60))
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.patch(
                "/api/sessions/test_agent/triggers/daily",
                json={"trigger_config": {"cron": "0 6 * * *"}},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["trigger_config"]["cron"] == "0 6 * * *"
            assert "daily" in session.active_timer_tasks
            assert session.active_timer_tasks["daily"] is not None
            assert session.available_triggers["daily"].trigger_config["cron"] == "0 6 * * *"
            session.active_timer_tasks["daily"].cancel()

    @pytest.mark.asyncio
    async def test_update_trigger_cron_rejects_invalid_expression(self, tmp_path):
        session = _make_session(tmp_dir=tmp_path)
        session.available_triggers["daily"] = TriggerDefinition(
            id="daily",
            trigger_type="timer",
            trigger_config={"cron": "0 5 * * *"},
            task="Run task",
        )
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.patch(
                "/api/sessions/test_agent/triggers/daily",
                json={"trigger_config": {"cron": "not a cron"}},
            )
            assert resp.status == 400


class TestExecution:
    @pytest.mark.asyncio
    async def test_trigger(self):
        session = _make_session()
        app = _make_app_with_session(session)
        app[APP_KEY_MANAGER].update_project(
            "default",
            {"policy_overrides": {"risk_tier": "low"}},
        )
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/trigger",
                json={"entry_point_id": "default", "input_data": {"msg": "hi"}},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["execution_id"] == "exec_test_123"

    @pytest.mark.asyncio
    async def test_trigger_not_found(self):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/nope/trigger",
                json={"entry_point_id": "default"},
            )
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_trigger_rejects_when_project_limit_reached(self):
        session = _make_session()
        app = _make_app_with_session(session)
        project_id = app[APP_KEY_MANAGER].default_project_id()
        session.project_id = project_id
        session.graph_runtime._mock_streams["default"].active_execution_ids.add("exec_running")
        app[APP_KEY_MANAGER].update_project(project_id, {"max_concurrent_runs": 1})
        app[APP_KEY_MANAGER].update_project(
            project_id,
            {"policy_overrides": {"risk_tier": "low"}},
        )

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/trigger",
                json={"entry_point_id": "default", "queue_if_busy": False},
            )
            assert resp.status == 409
            data = await resp.json()
            assert data["error"] == "Project execution limit reached"
            assert data["project_id"] == project_id
            assert data["active_runs"] >= 1
            assert data["max_concurrent_runs"] == 1

    @pytest.mark.asyncio
    async def test_trigger_queues_when_project_limit_reached(self):
        session = _make_session()
        app = _make_app_with_session(session)
        project_id = app[APP_KEY_MANAGER].default_project_id()
        session.project_id = project_id
        session.graph_runtime._mock_streams["default"].active_execution_ids.add("exec_running")
        app[APP_KEY_MANAGER].update_project(project_id, {"max_concurrent_runs": 1})
        app[APP_KEY_MANAGER].update_project(
            project_id,
            {"policy_overrides": {"risk_tier": "low"}},
        )

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/trigger",
                json={"entry_point_id": "default", "queue_if_busy": True, "priority": 5},
            )
            assert resp.status == 202
            data = await resp.json()
            assert data["queued"] is True
            assert data["project_id"] == project_id
            task_id = data["task_id"]

            queue_resp = await client.get(f"/api/projects/{project_id}/queue")
            assert queue_resp.status == 200
            queue_data = await queue_resp.json()
            queued_ids = [item["task_id"] for item in queue_data["queued"]]
            assert task_id in queued_ids

    @pytest.mark.asyncio
    async def test_trigger_respects_project_specific_limit(self):
        session = _make_session()
        app = _make_app_with_session(session)
        project_id = app[APP_KEY_MANAGER].default_project_id()
        session.project_id = project_id
        session.graph_runtime._mock_streams["default"].active_execution_ids.add("exec_running")
        app[APP_KEY_MANAGER].update_project(project_id, {"max_concurrent_runs": 2})
        app[APP_KEY_MANAGER].update_project(
            project_id,
            {"policy_overrides": {"risk_tier": "low"}},
        )

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/trigger",
                json={"entry_point_id": "default"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["execution_id"] == "exec_test_123"

    @pytest.mark.asyncio
    async def test_trigger_blocked_by_project_policy(self, tmp_path, monkeypatch):
        policy_path = tmp_path / "factory-policy.yaml"
        policy_path.write_text(
            "\n".join(
                [
                    "factory:",
                    "  default_risk_tier: low",
                    "risk_policy:",
                    "  critical:",
                    "    allowed: false",
                    "  low:",
                    "    allowed: true",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("HIVE_FACTORY_POLICY_PATH", str(policy_path))

        session = _make_session()
        app = _make_app_with_session(session)
        project_id = app[APP_KEY_MANAGER].default_project_id()
        session.project_id = project_id
        app[APP_KEY_MANAGER].update_project(project_id, {"policy_overrides": {"risk_tier": "critical"}})

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/trigger",
                json={"entry_point_id": "default"},
            )
            assert resp.status == 403
            data = await resp.json()
            assert data["error"] == "Execution blocked by project policy"
            assert data["effective_policy"]["risk_tier"] == "critical"

    @pytest.mark.asyncio
    async def test_inject(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/inject",
                json={"node_id": "node_a", "content": "answer"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["delivered"] is True

    @pytest.mark.asyncio
    async def test_inject_missing_node_id(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/inject",
                json={"content": "answer"},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_chat_goes_to_queen_when_not_waiting(self):
        """When worker is not awaiting input, chat goes to queen."""
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/chat",
                json={"message": "hello"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "queen"
            assert data["delivered"] is True

    @pytest.mark.asyncio
    async def test_chat_publishes_display_message_when_provided(self):
        session = _make_session()
        queen_node = session.queen_executor.node_registry["queen"]
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/chat",
                json={
                    "message": '[Worker asked: "Need approval"]\nUser answered: "Ship it"',
                    "display_message": "Ship it",
                },
            )
            assert resp.status == 200

        published_event = session.event_bus.publish.await_args.args[0]
        assert published_event.data["content"] == "Ship it"
        assert published_event.data["source"] == "web"
        queen_node.inject_event.assert_awaited_once_with(
            '[Worker asked: "Need approval"]\nUser answered: "Ship it"',
            is_client_input=True,
            image_content=None,
        )

    @pytest.mark.asyncio
    async def test_chat_publishes_client_message_id_when_provided(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/chat",
                json={"message": "hello", "client_message_id": "client-msg-99"},
            )
            assert resp.status == 200

        published_event = session.event_bus.publish.await_args.args[0]
        assert published_event.data["content"] == "hello"
        assert published_event.data["client_message_id"] == "client-msg-99"
        assert published_event.data["source"] == "web"

    @pytest.mark.asyncio
    async def test_chat_revive_path_publishes_client_input_received(self):
        session = _make_session(with_queen=False)
        app = _make_app_with_session(session)
        manager = app[APP_KEY_MANAGER]
        revived_executor = _make_queen_executor()

        async def _fake_revive(s: Session) -> None:
            s.queen_executor = revived_executor

        manager.revive_queen = AsyncMock(side_effect=_fake_revive)

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/chat",
                json={"message": "revive hello", "client_message_id": "revive-1"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "queen_revived"
            assert data["delivered"] is True

        published_event = session.event_bus.publish.await_args.args[0]
        assert published_event.data["content"] == "revive hello"
        assert published_event.data["client_message_id"] == "revive-1"
        assert published_event.data["source"] == "web"
        queen_node = revived_executor.node_registry["queen"]
        queen_node.inject_event.assert_awaited_once_with(
            "revive hello",
            is_client_input=True,
            image_content=None,
        )

    @pytest.mark.asyncio
    async def test_chat_prefers_queen_even_when_node_waiting(self):
        """When the queen is alive, /chat routes to queen even if a node is waiting."""
        session = _make_session()
        session.graph_runtime.find_awaiting_node = lambda: ("chat_node", "primary")
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/chat",
                json={"message": "user reply"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "queen"
            assert data["delivered"] is True

    @pytest.mark.asyncio
    async def test_chat_503_when_no_queen_or_worker(self):
        """Without queen or waiting worker, chat returns 503."""
        session = _make_session(with_queen=False)
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/chat",
                json={"message": "hello"},
            )
            assert resp.status == 503

    @pytest.mark.asyncio
    async def test_worker_input_route_removed(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/worker-input",
                json={"message": "hello"},
            )
            # No POST handler remains for this path; aiohttp falls through to an
            # overlapping GET/HEAD route and reports method-not-allowed.
            assert resp.status == 405

    @pytest.mark.asyncio
    async def test_chat_missing_message(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/chat",
                json={"message": ""},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_pause_no_active_executions(self):
        """Pause with no active executions returns stopped=False."""
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/pause",
                json={},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["stopped"] is False
            assert data["cancelled"] == []
            assert data["timers_paused"] is True

    @pytest.mark.asyncio
    async def test_pause_does_not_cancel_queen(self):
        """Pause should stop the worker but leave the queen running."""
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/pause",
                json={},
            )
            assert resp.status == 200
            # Queen's cancel_current_turn should NOT have been called
            queen_node = session.queen_executor.node_registry["queen"]
            queen_node.cancel_current_turn.assert_not_called()

    @pytest.mark.asyncio
    async def test_goal_progress(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/goal-progress")
            assert resp.status == 200
            data = await resp.json()
            assert data["progress"] == 0.5


class TestResume:
    @pytest.mark.asyncio
    async def test_resume_from_session_state(self, sample_session, tmp_agent_dir):
        """Direct state-based resume is rejected; checkpoint resume is required."""
        session_id, session_dir, state = sample_session
        tmp_path, agent_name, base = tmp_agent_dir

        session = _make_session(tmp_dir=tmp_path / ".hive" / "agents" / agent_name)
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/resume",
                json={"session_id": session_id},
            )
            assert resp.status == 400
            data = await resp.json()
            assert "checkpoint_id is required" in data["error"]

    @pytest.mark.asyncio
    async def test_resume_with_checkpoint(self, sample_session, tmp_agent_dir):
        """Resume using checkpoint-based recovery."""
        session_id, session_dir, state = sample_session
        tmp_path, agent_name, base = tmp_agent_dir

        session = _make_session(tmp_dir=tmp_path / ".hive" / "agents" / agent_name)
        session.graph_runtime.trigger = AsyncMock(return_value="exec_test_123")
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/resume",
                json={
                    "session_id": session_id,
                    "checkpoint_id": "cp_node_complete_node_a_001",
                },
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["checkpoint_id"] == "cp_node_complete_node_a_001"
            _, kwargs = session.graph_runtime.trigger.await_args
            assert kwargs["session_state"]["run_id"] == "__legacy_run__"

    @pytest.mark.asyncio
    async def test_resume_missing_session_id(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/resume",
                json={},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_resume_session_not_found(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/resume",
                json={"session_id": "session_nonexistent"},
            )
            assert resp.status == 404


class TestProjectsAPI:
    @pytest.mark.asyncio
    async def test_projects_crud_flow(self, tmp_agent_dir):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            list_resp = await client.get("/api/projects")
            assert list_resp.status == 200
            listed = await list_resp.json()
            assert "default_project_id" in listed
            assert isinstance(listed.get("projects"), list)

            create_resp = await client.post(
                "/api/projects",
                json={
                    "name": "Payments Core",
                    "description": "Core billing services",
                    "repository": "github.com/acme/payments-core",
                    "max_concurrent_runs": 3,
                    "execution_template": {
                        "github": {
                            "default_ref": "main",
                            "no_checks_policy": "success",
                        }
                    },
                },
            )
            assert create_resp.status == 201
            created = await create_resp.json()
            project_id = created["id"]
            assert created["name"] == "Payments Core"
            assert created["description"] == "Core billing services"
            assert created["repository"] == "github.com/acme/payments-core"
            assert created["max_concurrent_runs"] == 3
            assert created["execution_template"]["github"]["default_ref"] == "main"
            assert created["execution_template"]["github"]["no_checks_policy"] == "success"

            get_resp = await client.get(f"/api/projects/{project_id}")
            assert get_resp.status == 200
            fetched = await get_resp.json()
            assert fetched["id"] == project_id

            patch_resp = await client.patch(
                f"/api/projects/{project_id}",
                json={
                    "description": "Updated desc",
                    "repository": "github.com/acme/payments",
                    "max_concurrent_runs": 5,
                },
            )
            assert patch_resp.status == 200
            patched = await patch_resp.json()
            assert patched["description"] == "Updated desc"
            assert patched["repository"] == "github.com/acme/payments"
            assert patched["max_concurrent_runs"] == 5

            del_resp = await client.delete(f"/api/projects/{project_id}")
            assert del_resp.status == 200
            deleted = await del_resp.json()
            assert deleted["deleted"] == project_id

            get_deleted = await client.get(f"/api/projects/{project_id}")
            assert get_deleted.status == 404

    @pytest.mark.asyncio
    async def test_project_repository_provision_success_updates_project(self, monkeypatch):
        import framework.server.routes_projects as routes_projects

        captured: dict[str, object] = {}

        def _fake_create_repo(
            *,
            token: str,
            name: str,
            owner: str | None,
            visibility: str,
            description: str,
            initialize_readme: bool,
        ) -> dict:
            captured.update(
                {
                    "token": token,
                    "name": name,
                    "owner": owner,
                    "visibility": visibility,
                    "description": description,
                    "initialize_readme": initialize_readme,
                }
            )
            return {
                "name": name,
                "full_name": "acme/repo-provisioned",
                "html_url": "https://github.com/acme/repo-provisioned",
                "clone_url": "https://github.com/acme/repo-provisioned.git",
                "ssh_url": "git@github.com:acme/repo-provisioned.git",
                "default_branch": "main",
                "visibility": visibility,
                "private": visibility != "public",
            }

        monkeypatch.setattr(routes_projects, "_resolve_github_token", lambda _request: "ghp_test_token")
        monkeypatch.setattr(routes_projects, "_github_create_repository", _fake_create_repo)

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Provision Project")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                f"/api/projects/{pid}/repository/provision",
                json={
                    "name": "repo-provisioned",
                    "owner": "acme",
                    "visibility": "private",
                    "description": "Repository from Hive",
                    "initialize_readme": True,
                },
            )
            assert resp.status == 201
            data = await resp.json()
            assert data["repository"]["full_name"] == "acme/repo-provisioned"
            assert data["repository"]["html_url"] == "https://github.com/acme/repo-provisioned"
            assert data["project"]["repository"] == "https://github.com/acme/repo-provisioned"
            assert captured["token"] == "ghp_test_token"
            assert captured["owner"] == "acme"
            assert captured["name"] == "repo-provisioned"
            assert captured["visibility"] == "private"

            project = manager.get_project(pid)
            assert project is not None
            assert project.get("repository") == "https://github.com/acme/repo-provisioned"

    @pytest.mark.asyncio
    async def test_project_repository_provision_requires_token(self, monkeypatch):
        import framework.server.routes_projects as routes_projects

        monkeypatch.setattr(routes_projects, "_resolve_github_token", lambda _request: "")

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="No Token Provision")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                f"/api/projects/{pid}/repository/provision",
                json={"name": "repo-no-token"},
            )
            assert resp.status == 400
            data = await resp.json()
            assert "GitHub token is not configured" in data.get("error", "")

    @pytest.mark.asyncio
    async def test_project_repository_provision_maps_github_conflict(self, monkeypatch):
        import framework.server.routes_projects as routes_projects

        def _raise_conflict(**_kwargs):
            raise routes_projects._GitHubProvisionError("GitHub repository validation failed: name exists", status=409)

        monkeypatch.setattr(routes_projects, "_resolve_github_token", lambda _request: "ghp_test_token")
        monkeypatch.setattr(routes_projects, "_github_create_repository", _raise_conflict)

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Conflict Provision")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                f"/api/projects/{pid}/repository/provision",
                json={"name": "repo-conflict"},
            )
            assert resp.status == 409
            data = await resp.json()
            assert "validation failed" in data.get("error", "")

    @pytest.mark.asyncio
    async def test_project_repository_bind_validates_via_github_and_updates_project(self, monkeypatch):
        import framework.server.routes_projects as routes_projects

        def _fake_get_repo(*, token: str, repository: str) -> dict:
            assert token == "ghp_test_token"
            assert repository == "acme/existing-repo"
            return {
                "full_name": "acme/existing-repo",
                "html_url": "https://github.com/acme/existing-repo",
                "private": False,
                "default_branch": "main",
                "visibility": "public",
            }

        monkeypatch.setattr(routes_projects, "_resolve_github_token", lambda _request: "ghp_test_token")
        monkeypatch.setattr(routes_projects, "_github_get_repository", _fake_get_repo)

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Bind Project")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                f"/api/projects/{pid}/repository/bind",
                json={"repository": "https://github.com/acme/existing-repo"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["repository"]["full_name"] == "acme/existing-repo"
            assert data["project"]["repository"] == "https://github.com/acme/existing-repo"

            project = manager.get_project(pid)
            assert project is not None
            assert project.get("repository") == "https://github.com/acme/existing-repo"

    @pytest.mark.asyncio
    async def test_project_repository_bind_rejects_invalid_format(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Bind Invalid")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                f"/api/projects/{pid}/repository/bind",
                json={"repository": "not-a-github-repo"},
            )
            assert resp.status == 400
            data = await resp.json()
            assert "owner/name format" in data.get("error", "")

    @pytest.mark.asyncio
    async def test_create_project_requires_name(self, tmp_agent_dir):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/projects", json={"description": "missing name"})
            assert resp.status == 400
            data = await resp.json()
            assert "name is required" in data.get("error", "")

    @pytest.mark.asyncio
    async def test_create_project_rejects_invalid_max_runs(self, tmp_agent_dir):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/projects",
                json={"name": "Invalid", "max_concurrent_runs": 0},
            )
            assert resp.status == 400
            data = await resp.json()
            assert "max_concurrent_runs must be a positive integer" in data.get("error", "")

    @pytest.mark.asyncio
    async def test_project_workspace_path_create_and_update(self, tmp_path, tmp_agent_dir):
        workspace = tmp_path / "workspace-a"
        workspace.mkdir(parents=True, exist_ok=True)

        app = create_app()
        async with TestClient(TestServer(app)) as client:
            create_resp = await client.post(
                "/api/projects",
                json={
                    "name": "Workspace Project",
                    "workspace_path": str(workspace),
                },
            )
            assert create_resp.status == 201
            created = await create_resp.json()
            project_id = str(created.get("id"))
            assert created.get("workspace_path") == str(workspace)

            patch_resp = await client.patch(
                f"/api/projects/{project_id}",
                json={"workspace_path": ""},
            )
            assert patch_resp.status == 200
            patched = await patch_resp.json()
            assert patched.get("workspace_path") == ""

    @pytest.mark.asyncio
    async def test_project_environment_profile_update_and_preflight(self, tmp_agent_dir):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Env Profile Project")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            patch_resp = await client.patch(
                f"/api/projects/{pid}/environment",
                json={
                    "required_credentials": ["github", "google_docs"],
                    "services": [{"name": "redis", "endpoint": "", "required": True}],
                    "databases": [
                        {
                            "name": "main",
                            "engine": "postgres",
                            "endpoint": "postgresql://db.internal/app",
                            "required": True,
                        }
                    ],
                },
            )
            assert patch_resp.status == 200
            patched = await patch_resp.json()
            profile = patched.get("environment_profile") or {}
            assert profile.get("required_credentials") == ["github", "google_docs"]
            assert profile.get("services")[0]["name"] == "redis"

            get_resp = await client.get(f"/api/projects/{pid}/environment")
            assert get_resp.status == 200
            get_data = await get_resp.json()
            assert get_data.get("environment_profile", {}).get("databases", [])[0]["engine"] == "postgres"

            preflight_resp = await client.post(f"/api/projects/{pid}/environment/preflight", json={})
            assert preflight_resp.status == 202
            preflight = await preflight_resp.json()
            report = preflight.get("preflight") or {}
            assert report.get("ready") is False
            missing = report.get("missing") or {}
            assert "github" in (missing.get("credentials") or [])
            assert "redis" in (missing.get("services") or [])

    @pytest.mark.asyncio
    async def test_delete_project_conflict_with_active_sessions(self, tmp_agent_dir):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Backend")
        pid = str(created.get("id"))
        sess = _make_session(agent_id="busy-session")
        sess.project_id = pid
        manager._sessions[sess.id] = sess

        async with TestClient(TestServer(app)) as client:
            resp = await client.delete(f"/api/projects/{pid}")
            assert resp.status == 409
            data = await resp.json()
            assert "active sessions" in data.get("error", "")

            forced = await client.delete(f"/api/projects/{pid}?force=1")
            assert forced.status == 200

    @pytest.mark.asyncio
    async def test_delete_project_purges_autonomous_state(self, tmp_agent_dir):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        store = app[APP_KEY_AUTONOMOUS_STORE]
        created = manager.create_project(name="Project With Pipeline State")
        pid = str(created.get("id"))

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Task to purge",
                    "goal": "Ensure delete cascades pipeline state",
                    "acceptance_criteria": ["state removed on project delete"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            assert run_resp.status == 201

            assert any(t.project_id == pid for t in store.list_all_tasks())
            assert any(r.project_id == pid for r in store.list_all_runs())

            delete_resp = await client.delete(f"/api/projects/{pid}")
            assert delete_resp.status == 200
            delete_payload = await delete_resp.json()
            purged = delete_payload.get("autonomous_purged") or {}
            assert int(purged.get("tasks_removed", 0)) >= 1
            assert int(purged.get("runs_removed", 0)) >= 1
            assert all(t.project_id != pid for t in store.list_all_tasks())
            assert all(r.project_id != pid for r in store.list_all_runs())

    @pytest.mark.asyncio
    async def test_project_sessions_endpoint(self, tmp_agent_dir):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Frontend")
        pid = str(created.get("id"))
        sess = _make_session(agent_id="frontend-sess")
        sess.project_id = pid
        manager._sessions[sess.id] = sess

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(f"/api/projects/{pid}/sessions")
            assert resp.status == 200
            data = await resp.json()
            assert len(data["sessions"]) == 1
            assert data["sessions"][0]["session_id"] == "frontend-sess"
            assert data["sessions"][0]["project_id"] == pid

            missing = await client.get("/api/projects/nope/sessions")
            assert missing.status == 404

    @pytest.mark.asyncio
    async def test_project_policy_inheritance_and_overrides(self, tmp_path, monkeypatch):
        policy_path = tmp_path / "factory-policy.yaml"
        policy_path.write_text(
            "\n".join(
                [
                    "factory:",
                    "  default_risk_tier: low",
                    "  retry_limit_per_stage: 2",
                    "  budget_limit_usd_monthly: 250",
                    "risk_policy:",
                    "  low:",
                    "    plan_approval_required: false",
                    "    run_approval_required: false",
                    "    merge_approval_required: true",
                    "  high:",
                    "    plan_approval_required: true",
                    "    run_approval_required: true",
                    "    merge_approval_required: true",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("HIVE_FACTORY_POLICY_PATH", str(policy_path))

        app = create_app()
        async with TestClient(TestServer(app)) as client:
            created_resp = await client.post(
                "/api/projects",
                json={
                    "name": "Policy Project",
                    "policy_overrides": {"risk_tier": "high"},
                },
            )
            assert created_resp.status == 201
            created = await created_resp.json()
            pid = created["id"]

            get_policy = await client.get(f"/api/projects/{pid}/policy")
            assert get_policy.status == 200
            policy = await get_policy.json()
            assert policy["effective"]["risk_tier"] == "high"
            assert policy["effective"]["retry_limit_per_stage"] == 2
            assert policy["effective"]["budget_limit_usd_monthly"] == 250
            assert policy["effective"]["risk_controls"]["run_approval_required"] is True

            patch_policy = await client.patch(
                f"/api/projects/{pid}/policy",
                json={"retry_limit_per_stage": 5, "budget_limit_usd_monthly": 700.0},
            )
            assert patch_policy.status == 200
            patched = await patch_policy.json()
            assert patched["effective"]["retry_limit_per_stage"] == 5
            assert patched["effective"]["budget_limit_usd_monthly"] == 700.0

    @pytest.mark.asyncio
    async def test_project_policy_rejects_invalid_values(self, tmp_agent_dir):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Policy Invalid")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            bad_risk = await client.patch(
                f"/api/projects/{pid}/policy",
                json={"risk_tier": "extreme"},
            )
            assert bad_risk.status == 400
            bad_risk_data = await bad_risk.json()
            assert "risk_tier must be one of" in bad_risk_data.get("error", "")

            bad_retry = await client.patch(
                f"/api/projects/{pid}/policy",
                json={"retry_limit_per_stage": -1},
            )
            assert bad_retry.status == 400
            bad_retry_data = await bad_retry.json()
            assert "retry_limit_per_stage must be >= 0" in bad_retry_data.get("error", "")

    @pytest.mark.asyncio
    async def test_project_execution_template_defaults_and_update(self, tmp_path, monkeypatch):
        policy_path = tmp_path / "factory-policy-exec.yaml"
        policy_path.write_text(
            "\n".join(
                [
                    "factory:",
                    "  default_risk_tier: low",
                    "  retry_limit_per_stage: 2",
                    "risk_policy:",
                    "  low:",
                    "    run_approval_required: false",
                    "  high:",
                    "    run_approval_required: true",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("HIVE_FACTORY_POLICY_PATH", str(policy_path))

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Execution Template Project")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            get_default = await client.get(f"/api/projects/{pid}/execution-template")
            assert get_default.status == 200
            default_data = await get_default.json()
            assert default_data["effective"]["execution_template"]["default_flow"][0]["stage"] == "design"
            assert default_data["effective"]["execution_template"]["retry_policy"]["max_retries_per_stage"] == 1
            assert default_data["effective"]["policy"]["risk_tier"] == "low"

            patch_resp = await client.patch(
                f"/api/projects/{pid}/execution-template",
                json={
                    "execution_template": {
                        "default_flow": [
                            {"stage": "design", "mode": "queen_plan", "model_profile": "gpt-5.4-thinking"},
                            {"stage": "implement", "mode": "worker_execute", "model_profile": "gemini-3.1-pro-high"},
                            {"stage": "review", "mode": "worker_review", "model_profile": "gpt-5.3-codex"},
                            {"stage": "validate", "mode": "worker_validate", "model_profile": "gpt-5.3-codex"},
                        ],
                        "retry_policy": {"max_retries_per_stage": 2, "escalate_on": ["review"]},
                        "github": {
                            "default_ref": "main",
                            "no_checks_policy": "manual_pending",
                        },
                    },
                    "policy_binding": {
                        "risk_tier": "high",
                        "retry_limit_per_stage": 4,
                        "budget_limit_usd_monthly": 300.0,
                    },
                },
            )
            assert patch_resp.status == 200
            patched = await patch_resp.json()
            assert patched["effective"]["execution_template"]["default_flow"][0]["model_profile"] == "gpt-5.4-thinking"
            assert patched["effective"]["execution_template"]["retry_policy"]["max_retries_per_stage"] == 2
            assert patched["effective"]["execution_template"]["github"]["default_ref"] == "main"
            assert patched["effective"]["execution_template"]["github"]["no_checks_policy"] == "manual_pending"
            assert patched["effective"]["policy"]["risk_tier"] == "high"
            assert patched["effective"]["policy"]["retry_limit_per_stage"] == 4

            policy_resp = await client.get(f"/api/projects/{pid}/policy")
            assert policy_resp.status == 200
            policy_data = await policy_resp.json()
            assert policy_data["effective"]["risk_tier"] == "high"
            assert policy_data["effective"]["retry_limit_per_stage"] == 4

    @pytest.mark.asyncio
    async def test_project_execution_template_rejects_invalid_payload(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Execution Template Invalid")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            bad = await client.patch(
                f"/api/projects/{pid}/execution-template",
                json={"execution_template": {"default_flow": []}},
            )
            assert bad.status == 400
            bad_data = await bad.json()
            assert "default_flow must be a non-empty array" in bad_data.get("error", "")

            bad_policy = await client.patch(
                f"/api/projects/{pid}/execution-template",
                json={"execution_template": {"github": {"no_checks_policy": "sometimes"}}},
            )
            assert bad_policy.status == 400
            bad_policy_data = await bad_policy.json()
            assert "github.no_checks_policy must be one of" in bad_policy_data.get("error", "")

    @pytest.mark.asyncio
    async def test_project_retention_inheritance_and_overrides(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Retention Project")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            get_retention = await client.get(f"/api/projects/{pid}/retention")
            assert get_retention.status == 200
            retention = await get_retention.json()
            assert retention["effective"]["history_days"] == 30
            assert retention["effective"]["min_sessions_to_keep"] == 20
            assert retention["effective"]["archive_enabled"] is True

            patch_retention = await client.patch(
                f"/api/projects/{pid}/retention",
                json={"history_days": 14, "min_sessions_to_keep": 5},
            )
            assert patch_retention.status == 200
            patched = await patch_retention.json()
            assert patched["effective"]["history_days"] == 14
            assert patched["effective"]["min_sessions_to_keep"] == 5

    @pytest.mark.asyncio
    async def test_project_retention_apply_archives_old_sessions(self, tmp_path, tmp_agent_dir):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Retention Apply")
        pid = created["id"]

        sessions_dir = tmp_path / ".hive" / "queen" / "session"
        old_session = sessions_dir / "session_old"
        new_session = sessions_dir / "session_new"
        (old_session / "conversations" / "parts").mkdir(parents=True, exist_ok=True)
        (new_session / "conversations" / "parts").mkdir(parents=True, exist_ok=True)

        now = time.time()
        (old_session / "meta.json").write_text(
            json.dumps({"project_id": pid, "created_at": now - (45 * 86400)}),
            encoding="utf-8",
        )
        (new_session / "meta.json").write_text(
            json.dumps({"project_id": pid, "created_at": now - (2 * 86400)}),
            encoding="utf-8",
        )

        archive_root = tmp_path / "archive-target"
        async with TestClient(TestServer(app)) as client:
            dry_run = await client.post(
                f"/api/projects/{pid}/retention/apply",
                json={
                    "dry_run": True,
                    "history_days": 30,
                    "min_sessions_to_keep": 0,
                    "archive_enabled": True,
                    "archive_root": str(archive_root),
                },
            )
            assert dry_run.status == 200
            dry_data = await dry_run.json()
            candidate_ids = {c["session_id"] for c in dry_data["plan"]["candidates"]}
            assert "session_old" in candidate_ids
            assert "session_new" not in candidate_ids

            apply_resp = await client.post(
                f"/api/projects/{pid}/retention/apply",
                json={
                    "dry_run": False,
                    "history_days": 30,
                    "min_sessions_to_keep": 0,
                    "archive_enabled": True,
                    "archive_root": str(archive_root),
                },
            )
            assert apply_resp.status == 200
            applied = await apply_resp.json()
            assert "session_old" in applied["applied"]["archived"]
            assert (archive_root / pid / "session_old").exists()
            assert not old_session.exists()
            assert new_session.exists()

    @pytest.mark.asyncio
    async def test_project_onboarding_bootstraps_manifest_and_runs_dry_run(self, tmp_path, tmp_agent_dir):
        repo_dir = tmp_path / "repo-a"
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / ".git").mkdir()
        (repo_dir / "README.md").write_text("# Repo A\n", encoding="utf-8")

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Onboarding Project", repository="github.com/acme/repo-a")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                f"/api/projects/{pid}/onboarding",
                json={
                    "workspace_path": str(repo_dir),
                    "stack": "python",
                    "repo_type": "single",
                    "dry_run_command": "test -f automation/hive.manifest.yaml",
                },
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["ready"] is True
            assert data["manifest"]["exists"] is True
            assert data["dry_run"]["status"] == "ok"

            manifest_path = repo_dir / "automation" / "hive.manifest.yaml"
            assert manifest_path.exists()
            manifest_text = manifest_path.read_text(encoding="utf-8")
            assert 'stack: "python"' in manifest_text
            assert "automation:" in manifest_text
            assert "execution:" in manifest_text
            assert 'stage: "design"' in manifest_text
            assert 'stage: "implement"' in manifest_text
            assert 'stage: "review"' in manifest_text

            project = manager.get_project(pid)
            assert project is not None
            assert project.get("workspace_path") == str(repo_dir)

    @pytest.mark.asyncio
    async def test_project_onboarding_rejects_invalid_stack(self, tmp_agent_dir):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Onboarding Invalid", repository="github.com/acme/repo-invalid")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                f"/api/projects/{pid}/onboarding",
                json={"stack": "php"},
            )
            assert resp.status == 400
            data = await resp.json()
            assert "stack must be one of" in data.get("error", "")

    @pytest.mark.asyncio
    async def test_project_onboarding_reports_missing_toolchain_runtime(self, tmp_path, monkeypatch):
        import framework.server.project_onboarding as project_onboarding

        repo_dir = tmp_path / "repo-toolchain"
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / ".git").mkdir()
        (repo_dir / "README.md").write_text("# Toolchain Repo\n", encoding="utf-8")
        (repo_dir / "package.json").write_text('{"name":"toolchain-repo"}\n', encoding="utf-8")

        original_which = project_onboarding.shutil.which

        def _fake_which(name: str):
            if name in {"node", "npm"}:
                return None
            return original_which(name)

        monkeypatch.setattr(project_onboarding.shutil, "which", _fake_which)

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Toolchain Project", repository="github.com/acme/toolchain-repo")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                f"/api/projects/{pid}/onboarding",
                json={
                    "workspace_path": str(repo_dir),
                    "stack": "node",
                    "repo_type": "single",
                    "dry_run_command": "test -f package.json",
                },
            )
            assert resp.status == 202
            data = await resp.json()
            assert data["ready"] is False
            toolchain_check = next(c for c in data["checks"] if c["id"] == "toolchain_runtime")
            assert toolchain_check["status"] == "fail"
            assert "Missing binaries for stack 'node'" in toolchain_check["message"]

    @pytest.mark.asyncio
    async def test_project_toolchain_profile_plan_and_approve(self, tmp_path, monkeypatch):
        import framework.server.routes_projects as routes_projects

        workspace = tmp_path / "toolchain-workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")

        def _plan(*, workspace_path: str | None, repository: str | None):
            return {
                "workspace": workspace_path or "",
                "repository": repository or "",
                "toolchains": ["node"],
                "marker_hits": {"node": ["package.json"]},
                "docker_build_args": {
                    "HIVE_DOCKER_INSTALL_GO": 0,
                    "HIVE_DOCKER_INSTALL_JAVA": 0,
                    "HIVE_DOCKER_INSTALL_NODE": 1,
                    "HIVE_DOCKER_INSTALL_RUST": 0,
                },
                "recommended_stack": "node",
                "plan_fingerprint": "ABCDEF12",
                "confirm_token": "APPLY_NODE_ABCDEF12",
                "generated_at": 123.0,
            }

        monkeypatch.setattr(routes_projects, "detect_toolchain_plan", _plan)

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(
            name="Toolchain Approve",
            repository="https://github.com/acme/toolchain-approve",
        )
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            planned_resp = await client.post(
                f"/api/projects/{pid}/toolchain-profile/plan",
                json={"workspace_path": str(workspace)},
            )
            assert planned_resp.status == 200
            planned = await planned_resp.json()
            assert planned["pending_plan"]["plan"]["confirm_token"] == "APPLY_NODE_ABCDEF12"
            assert "apply_hive_toolchain_profile.sh" in planned["instructions"]["apply_command"]

            bad_confirm = await client.post(
                f"/api/projects/{pid}/toolchain-profile/approve",
                json={"confirm_token": "APPLY_NODE_WRONG"},
            )
            assert bad_confirm.status == 409

            ok_confirm = await client.post(
                f"/api/projects/{pid}/toolchain-profile/approve",
                json={"confirm_token": "APPLY_NODE_ABCDEF12"},
            )
            assert ok_confirm.status == 200
            approved = await ok_confirm.json()
            assert approved["status"] == "approved"
            assert approved["approved_plan"]["approved_token"] == "APPLY_NODE_ABCDEF12"

            profile_resp = await client.get(f"/api/projects/{pid}/toolchain-profile")
            assert profile_resp.status == 200
            profile_payload = await profile_resp.json()
            profile = profile_payload.get("toolchain_profile") or {}
            assert profile.get("pending_plan") is None
            assert isinstance(profile.get("approved_plan"), dict)

    @pytest.mark.asyncio
    async def test_project_toolchain_profile_approve_revalidate_detects_plan_drift(self, tmp_path, monkeypatch):
        import framework.server.routes_projects as routes_projects

        workspace = tmp_path / "toolchain-workspace-drift"
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")

        calls = {"count": 0}

        def _plan(*, workspace_path: str | None, repository: str | None):
            calls["count"] += 1
            token = "APPLY_NODE_OLD11111" if calls["count"] == 1 else "APPLY_NODE_NEW22222"
            fingerprint = "OLD11111" if calls["count"] == 1 else "NEW22222"
            return {
                "workspace": workspace_path or "",
                "repository": repository or "",
                "toolchains": ["node"],
                "marker_hits": {"node": ["package.json"]},
                "docker_build_args": {
                    "HIVE_DOCKER_INSTALL_GO": 0,
                    "HIVE_DOCKER_INSTALL_JAVA": 0,
                    "HIVE_DOCKER_INSTALL_NODE": 1,
                    "HIVE_DOCKER_INSTALL_RUST": 0,
                },
                "recommended_stack": "node",
                "plan_fingerprint": fingerprint,
                "confirm_token": token,
                "generated_at": 123.0,
            }

        monkeypatch.setattr(routes_projects, "detect_toolchain_plan", _plan)

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Toolchain Drift")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            planned_resp = await client.post(
                f"/api/projects/{pid}/toolchain-profile/plan",
                json={"workspace_path": str(workspace)},
            )
            assert planned_resp.status == 200
            planned = await planned_resp.json()
            assert planned["pending_plan"]["plan"]["confirm_token"] == "APPLY_NODE_OLD11111"

            approve_resp = await client.post(
                f"/api/projects/{pid}/toolchain-profile/approve",
                json={"confirm_token": "APPLY_NODE_OLD11111"},
            )
            assert approve_resp.status == 409
            drift = await approve_resp.json()
            assert "toolchain plan changed" in drift.get("error", "")
            refreshed = drift.get("pending_plan", {}).get("plan", {})
            assert refreshed.get("confirm_token") == "APPLY_NODE_NEW22222"

    @pytest.mark.asyncio
    async def test_project_templates_endpoint(self):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/projects/templates")
            assert resp.status == 200
            data = await resp.json()
            assert isinstance(data.get("templates"), list)
            ids = {str(item.get("id")) for item in data["templates"]}
            assert "frontend-web" in ids
            assert "backend-python-api" in ids
            assert "fullstack-platform" in ids

    @pytest.mark.asyncio
    async def test_project_onboarding_uses_template_defaults(self, tmp_path):
        repo_dir = tmp_path / "repo-template"
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / ".git").mkdir()
        (repo_dir / "README.md").write_text("# Template Repo\n", encoding="utf-8")

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Template Project", repository="github.com/acme/template-repo")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                f"/api/projects/{pid}/onboarding",
                json={
                    "template_id": "backend-python-api",
                    "workspace_path": str(repo_dir),
                    "dry_run_command": "test -f automation/hive.manifest.yaml",
                },
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["ready"] is True
            assert data["manifest"]["exists"] is True
            assert data["dry_run"]["status"] == "ok"

            manifest_path = repo_dir / "automation" / "hive.manifest.yaml"
            manifest_text = manifest_path.read_text(encoding="utf-8")
            assert 'stack: "python"' in manifest_text
            assert 'typecheck:\n    - "uv run pyright"' in manifest_text
            assert "execution:" in manifest_text
            assert 'model_profile: "review_validation"' in manifest_text

    @pytest.mark.asyncio
    async def test_project_metrics_endpoint(self, tmp_agent_dir):
        tmp_path, _agent_name, _base = tmp_agent_dir
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Metrics Project")
        pid = created["id"]

        session_id = "session_metrics_001"
        session_dir = tmp_path / ".hive" / "queen" / "session" / session_id
        (session_dir / "conversations" / "parts").mkdir(parents=True, exist_ok=True)
        (session_dir / "meta.json").write_text(
            json.dumps({"project_id": pid, "created_at": 1_700_000_000}),
            encoding="utf-8",
        )
        (session_dir / "conversations" / "parts" / "0001.json").write_text(
            json.dumps({"seq": 1, "role": "user", "content": "Implement feature X"}),
            encoding="utf-8",
        )
        (session_dir / "conversations" / "parts" / "0002.json").write_text(
            json.dumps({"seq": 2, "role": "assistant", "content": "Working on it"}),
            encoding="utf-8",
        )
        (session_dir / "events.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "execution_started",
                            "execution_id": "exec_ok",
                            "timestamp": "2026-04-08T10:00:00+00:00",
                        }
                    ),
                    json.dumps(
                        {
                            "type": "execution_completed",
                            "execution_id": "exec_ok",
                            "timestamp": "2026-04-08T10:00:20+00:00",
                        }
                    ),
                    json.dumps(
                        {
                            "type": "execution_started",
                            "execution_id": "exec_fail",
                            "timestamp": "2026-04-08T10:01:00+00:00",
                        }
                    ),
                    json.dumps(
                        {
                            "type": "execution_failed",
                            "execution_id": "exec_fail",
                            "timestamp": "2026-04-08T10:01:10+00:00",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(f"/api/projects/{pid}/metrics")
            assert resp.status == 200
            data = await resp.json()
            assert data["project_id"] == pid
            assert data["summary"]["historical_sessions"] == 1
            assert data["summary"]["executions_total"] == 2
            assert data["kpis"]["success_rate"] == 0.5
            assert data["kpis"]["cycle_time_seconds_p50"] == 15.0
            assert data["kpis"]["intervention_ratio"] == 0.5

    @pytest.mark.asyncio
    async def test_projects_metrics_comparison_endpoint(self, tmp_agent_dir):
        tmp_path, _agent_name, _base = tmp_agent_dir
        app = create_app()
        manager = app[APP_KEY_MANAGER]

        p1 = manager.create_project(name="Project A")
        p2 = manager.create_project(name="Project B")

        s1_dir = tmp_path / ".hive" / "queen" / "session" / "session_cmp_a"
        (s1_dir / "conversations" / "parts").mkdir(parents=True, exist_ok=True)
        (s1_dir / "meta.json").write_text(json.dumps({"project_id": p1["id"]}), encoding="utf-8")
        (s1_dir / "events.jsonl").write_text(
            json.dumps(
                {
                    "type": "execution_completed",
                    "execution_id": "exec_a",
                    "timestamp": "2026-04-08T10:00:00+00:00",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        s2_dir = tmp_path / ".hive" / "queen" / "session" / "session_cmp_b"
        (s2_dir / "conversations" / "parts").mkdir(parents=True, exist_ok=True)
        (s2_dir / "meta.json").write_text(json.dumps({"project_id": p2["id"]}), encoding="utf-8")
        (s2_dir / "events.jsonl").write_text(
            json.dumps(
                {
                    "type": "execution_failed",
                    "execution_id": "exec_b",
                    "timestamp": "2026-04-08T10:00:00+00:00",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/projects/metrics")
            assert resp.status == 200
            data = await resp.json()
            assert isinstance(data.get("projects"), list)
            assert len(data["projects"]) >= 2
            top = data["projects"][0]
            assert top["project"]["id"] in {p1["id"], p2["id"], "default"}


class TestStop:
    @pytest.mark.asyncio
    async def test_stop_found(self):
        session = _make_session()
        # Put a mock task in the stream so cancel_execution returns True
        session.graph_runtime._mock_streams["default"]._execution_tasks["exec_abc"] = MagicMock()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/stop",
                json={"execution_id": "exec_abc"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["stopped"] is True

    @pytest.mark.asyncio
    async def test_stop_not_found(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/stop",
                json={"execution_id": "nonexistent"},
            )
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_stop_missing_execution_id(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/stop",
                json={},
            )
            assert resp.status == 400


class TestReplay:
    @pytest.mark.asyncio
    async def test_replay_success(self, sample_session, tmp_agent_dir):
        session_id, session_dir, state = sample_session
        tmp_path, agent_name, base = tmp_agent_dir

        session = _make_session(tmp_dir=tmp_path / ".hive" / "agents" / agent_name)
        session.graph_runtime.trigger = AsyncMock(return_value="exec_test_123")
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/replay",
                json={
                    "session_id": session_id,
                    "checkpoint_id": "cp_node_complete_node_a_001",
                },
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["execution_id"] == "exec_test_123"
            assert data["replayed_from"] == session_id
            _, kwargs = session.graph_runtime.trigger.await_args
            assert kwargs["session_state"]["run_id"] == "__legacy_run__"

    @pytest.mark.asyncio
    async def test_replay_missing_fields(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/replay",
                json={"session_id": "s1"},
            )
            assert resp.status == 400  # missing checkpoint_id

            resp2 = await client.post(
                "/api/sessions/test_agent/replay",
                json={"checkpoint_id": "cp1"},
            )
            assert resp2.status == 400  # missing session_id

    @pytest.mark.asyncio
    async def test_replay_checkpoint_not_found(self, sample_session, tmp_agent_dir):
        session_id, session_dir, state = sample_session
        tmp_path, agent_name, base = tmp_agent_dir

        session = _make_session(tmp_dir=tmp_path / ".hive" / "agents" / agent_name)
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sessions/test_agent/replay",
                json={
                    "session_id": session_id,
                    "checkpoint_id": "nonexistent_cp",
                },
            )
            assert resp.status == 404


class TestGraphNodes:
    @pytest.mark.asyncio
    async def test_list_nodes(self, nodes_and_edges):
        nodes, edges = nodes_and_edges
        session = _make_session(nodes=nodes, edges=edges)
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/graphs/primary/nodes")
            assert resp.status == 200
            data = await resp.json()
            assert len(data["nodes"]) == 2
            node_ids = [n["id"] for n in data["nodes"]]
            assert "node_a" in node_ids
            assert "node_b" in node_ids
            # Edges and entry_node must be present
            assert "edges" in data
            assert "entry_node" in data

    @pytest.mark.asyncio
    async def test_list_nodes_includes_edges(self, nodes_and_edges):
        nodes, edges = nodes_and_edges
        graph = MockGraphSpec(nodes=nodes, edges=edges, entry_node="node_a")
        rt = MockRuntime(graph=graph)
        session = _make_session(runtime=rt)
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/graphs/primary/nodes")
            assert resp.status == 200
            data = await resp.json()

            # Edges present and correct
            assert "edges" in data
            assert len(data["edges"]) == 1
            assert data["edges"][0]["source"] == "node_a"
            assert data["edges"][0]["target"] == "node_b"
            assert data["edges"][0]["condition"] == "on_success"
            assert data["edges"][0]["priority"] == 0

            # Entry node present
            assert data["entry_node"] == "node_a"

    @pytest.mark.asyncio
    async def test_list_nodes_with_session_enrichment(
        self, nodes_and_edges, sample_session, tmp_agent_dir
    ):
        session_id, session_dir, state = sample_session
        tmp_path, agent_name, base = tmp_agent_dir
        nodes, edges = nodes_and_edges

        session = _make_session(
            tmp_dir=tmp_path / ".hive" / "agents" / agent_name,
            nodes=nodes,
            edges=edges,
        )
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(
                f"/api/sessions/test_agent/graphs/primary/nodes?session_id={session_id}"
            )
            assert resp.status == 200
            data = await resp.json()
            node_map = {n["id"]: n for n in data["nodes"]}

            assert node_map["node_a"]["visit_count"] == 1
            assert node_map["node_a"]["in_path"] is True
            assert node_map["node_b"]["is_current"] is True
            assert node_map["node_b"]["has_failures"] is True

    @pytest.mark.asyncio
    async def test_list_nodes_graph_not_found(self):
        session = _make_session()
        app = _make_app_with_session(session)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/graphs/nonexistent/nodes")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_get_node(self, nodes_and_edges):
        nodes, edges = nodes_and_edges
        session = _make_session(nodes=nodes, edges=edges)
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/graphs/primary/nodes/node_a")
            assert resp.status == 200
            data = await resp.json()
            assert data["id"] == "node_a"
            assert data["name"] == "Node A"
            assert data["input_keys"] == ["user_request"]
            assert data["output_keys"] == ["result"]
            assert data["success_criteria"] == "Produce a valid result"
            # Should include edges from this node
            assert len(data["edges"]) == 1
            assert data["edges"][0]["target"] == "node_b"

    @pytest.mark.asyncio
    async def test_node_detail_includes_system_prompt(self, nodes_and_edges):
        """system_prompt should appear in the single-node GET response."""
        nodes, edges = nodes_and_edges
        session = _make_session(nodes=nodes, edges=edges)
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/graphs/primary/nodes/node_a")
            assert resp.status == 200
            data = await resp.json()
            assert "system_prompt" in data
            assert (
                data["system_prompt"] == "You are a helpful assistant that produces valid results."
            )

            # Node without system_prompt should return empty string
            resp2 = await client.get("/api/sessions/test_agent/graphs/primary/nodes/node_b")
            assert resp2.status == 200
            data2 = await resp2.json()
            assert data2["system_prompt"] == ""

    @pytest.mark.asyncio
    async def test_get_node_not_found(self, nodes_and_edges):
        nodes, edges = nodes_and_edges
        session = _make_session(nodes=nodes, edges=edges)
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/graphs/primary/nodes/nonexistent")
            assert resp.status == 404


class TestNodeCriteria:
    @pytest.mark.asyncio
    async def test_criteria_static(self, nodes_and_edges):
        nodes, edges = nodes_and_edges
        session = _make_session(nodes=nodes, edges=edges)
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/graphs/primary/nodes/node_a/criteria")
            assert resp.status == 200
            data = await resp.json()
            assert data["node_id"] == "node_a"
            assert data["success_criteria"] == "Produce a valid result"
            assert data["output_keys"] == ["result"]

    @pytest.mark.asyncio
    async def test_criteria_with_log_enrichment(
        self, nodes_and_edges, sample_session, tmp_agent_dir
    ):
        """Criteria endpoint enriched with last execution from logs."""
        session_id, session_dir, state = sample_session
        tmp_path, agent_name, base = tmp_agent_dir
        nodes, edges = nodes_and_edges

        # Create a real RuntimeLogStore pointed at the temp agent dir
        from framework.runtime.runtime_log_store import RuntimeLogStore

        log_store = RuntimeLogStore(base)

        session = _make_session(
            tmp_dir=tmp_path / ".hive" / "agents" / agent_name,
            nodes=nodes,
            edges=edges,
            log_store=log_store,
        )
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(
                f"/api/sessions/test_agent/graphs/primary/nodes/node_b/criteria"
                f"?session_id={session_id}"
            )
            assert resp.status == 200
            data = await resp.json()
            assert "last_execution" in data
            assert data["last_execution"]["success"] is False
            assert data["last_execution"]["error"] == "timeout"
            assert data["last_execution"]["retry_count"] == 2
            assert data["last_execution"]["needs_attention"] is True

    @pytest.mark.asyncio
    async def test_criteria_node_not_found(self, nodes_and_edges):
        nodes, edges = nodes_and_edges
        session = _make_session(nodes=nodes, edges=edges)
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(
                "/api/sessions/test_agent/graphs/primary/nodes/nonexistent/criteria"
            )
            assert resp.status == 404


class TestLogs:
    @pytest.mark.asyncio
    async def test_logs_no_log_store(self):
        """Agent without log store returns 404."""
        session = _make_session()
        session.graph_runtime._runtime_log_store = None
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/logs")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_logs_list_summaries(self, sample_session, tmp_agent_dir):
        session_id, session_dir, state = sample_session
        tmp_path, agent_name, base = tmp_agent_dir

        from framework.runtime.runtime_log_store import RuntimeLogStore

        log_store = RuntimeLogStore(base)
        session = _make_session(
            tmp_dir=tmp_path / ".hive" / "agents" / agent_name,
            log_store=log_store,
        )
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/logs")
            assert resp.status == 200
            data = await resp.json()
            assert "logs" in data
            assert len(data["logs"]) >= 1
            assert data["logs"][0]["run_id"] == session_id

    @pytest.mark.asyncio
    async def test_logs_list_summaries_with_custom_id(self, custom_id_session, tmp_agent_dir):
        session_id, session_dir, state = custom_id_session
        tmp_path, agent_name, base = tmp_agent_dir

        from framework.runtime.runtime_log_store import RuntimeLogStore

        log_store = RuntimeLogStore(base)
        session = _make_session(
            tmp_dir=tmp_path / ".hive" / "agents" / agent_name,
            log_store=log_store,
        )
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/logs")
            assert resp.status == 200
            data = await resp.json()
            assert "logs" in data
            assert len(data["logs"]) >= 1
            assert data["logs"][0]["run_id"] == session_id

    @pytest.mark.asyncio
    async def test_logs_session_summary(self, sample_session, tmp_agent_dir):
        session_id, session_dir, state = sample_session
        tmp_path, agent_name, base = tmp_agent_dir

        from framework.runtime.runtime_log_store import RuntimeLogStore

        log_store = RuntimeLogStore(base)
        session = _make_session(
            tmp_dir=tmp_path / ".hive" / "agents" / agent_name,
            log_store=log_store,
        )
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(
                f"/api/sessions/test_agent/logs?session_id={session_id}&level=summary"
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["run_id"] == session_id
            assert data["status"] == "paused"

    @pytest.mark.asyncio
    async def test_logs_session_details(self, sample_session, tmp_agent_dir):
        session_id, session_dir, state = sample_session
        tmp_path, agent_name, base = tmp_agent_dir

        from framework.runtime.runtime_log_store import RuntimeLogStore

        log_store = RuntimeLogStore(base)
        session = _make_session(
            tmp_dir=tmp_path / ".hive" / "agents" / agent_name,
            log_store=log_store,
        )
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(
                f"/api/sessions/test_agent/logs?session_id={session_id}&level=details"
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["session_id"] == session_id
            assert len(data["nodes"]) == 2
            assert data["nodes"][0]["node_id"] == "node_a"

    @pytest.mark.asyncio
    async def test_logs_session_tools(self, sample_session, tmp_agent_dir):
        session_id, session_dir, state = sample_session
        tmp_path, agent_name, base = tmp_agent_dir

        from framework.runtime.runtime_log_store import RuntimeLogStore

        log_store = RuntimeLogStore(base)
        session = _make_session(
            tmp_dir=tmp_path / ".hive" / "agents" / agent_name,
            log_store=log_store,
        )
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(
                f"/api/sessions/test_agent/logs?session_id={session_id}&level=tools"
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["session_id"] == session_id
            assert len(data["steps"]) == 2


class TestNodeLogs:
    @pytest.mark.asyncio
    async def test_node_logs(self, sample_session, tmp_agent_dir, nodes_and_edges):
        session_id, session_dir, state = sample_session
        tmp_path, agent_name, base = tmp_agent_dir
        nodes, edges = nodes_and_edges

        from framework.runtime.runtime_log_store import RuntimeLogStore

        log_store = RuntimeLogStore(base)
        session = _make_session(
            tmp_dir=tmp_path / ".hive" / "agents" / agent_name,
            nodes=nodes,
            edges=edges,
            log_store=log_store,
        )
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(
                f"/api/sessions/test_agent/graphs/primary/nodes/node_a/logs?session_id={session_id}"
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["node_id"] == "node_a"
            assert data["session_id"] == session_id
            # Only node_a's details
            assert len(data["details"]) == 1
            assert data["details"][0]["node_id"] == "node_a"
            # Only node_a's tool logs
            assert len(data["tool_logs"]) == 1
            assert data["tool_logs"][0]["node_id"] == "node_a"

    @pytest.mark.asyncio
    async def test_node_logs_missing_session_id(self, nodes_and_edges):
        nodes, edges = nodes_and_edges
        from framework.runtime.runtime_log_store import RuntimeLogStore

        log_store = RuntimeLogStore(Path("/tmp/dummy"))
        session = _make_session(nodes=nodes, edges=edges, log_store=log_store)
        app = _make_app_with_session(session)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/test_agent/graphs/primary/nodes/node_a/logs")
            assert resp.status == 400


class TestCredentials:
    """Tests for credential CRUD routes (/api/credentials)."""

    def _make_app(self, initial_creds=None):
        """Create app with in-memory credential store."""
        from framework.credentials.store import CredentialStore

        app = create_app()
        app[APP_KEY_CREDENTIAL_STORE] = CredentialStore.for_testing(initial_creds or {})
        return app

    @pytest.mark.asyncio
    async def test_list_credentials_empty(self):
        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/credentials")
            assert resp.status == 200
            data = await resp.json()
            assert data["credentials"] == []

    @pytest.mark.asyncio
    async def test_save_and_list_credential(self):
        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/credentials",
                json={"credential_id": "brave_search", "keys": {"api_key": "test-key-123"}},
            )
            assert resp.status == 201
            data = await resp.json()
            assert data["saved"] == "brave_search"

            resp2 = await client.get("/api/credentials")
            data2 = await resp2.json()
            assert len(data2["credentials"]) == 1
            assert data2["credentials"][0]["credential_id"] == "brave_search"
            assert "api_key" in data2["credentials"][0]["key_names"]
            # Secret value must NOT appear
            assert "test-key-123" not in json.dumps(data2)

    @pytest.mark.asyncio
    async def test_get_credential(self):
        app = self._make_app({"test_cred": {"api_key": "secret-value"}})
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/credentials/test_cred")
            assert resp.status == 200
            data = await resp.json()
            assert data["credential_id"] == "test_cred"
            assert "api_key" in data["key_names"]
            # Secret value must NOT appear
            assert "secret-value" not in json.dumps(data)

    @pytest.mark.asyncio
    async def test_get_credential_not_found(self):
        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/credentials/nonexistent")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_delete_credential(self):
        app = self._make_app({"test_cred": {"api_key": "val"}})
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/credentials/test_cred")
            assert resp.status == 200
            data = await resp.json()
            assert data["deleted"] is True

            # Verify it's gone
            resp2 = await client.get("/api/credentials/test_cred")
            assert resp2.status == 404

    @pytest.mark.asyncio
    async def test_delete_credential_not_found(self):
        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/credentials/nonexistent")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_save_credential_missing_fields(self):
        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/credentials", json={})
            assert resp.status == 400

            resp2 = await client.post("/api/credentials", json={"credential_id": "x"})
            assert resp2.status == 400

    @pytest.mark.asyncio
    async def test_save_overwrites_existing(self):
        app = self._make_app({"test_cred": {"api_key": "old-value"}})
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/credentials",
                json={"credential_id": "test_cred", "keys": {"api_key": "new-value"}},
            )
            assert resp.status == 201

            store = app[APP_KEY_CREDENTIAL_STORE]
            assert store.get_key("test_cred", "api_key") == "new-value"

    @pytest.mark.asyncio
    async def test_credentials_readiness_unknown_bundle(self):
        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/credentials/readiness?bundle=unknown")
            assert resp.status == 400
            data = await resp.json()
            assert "Unknown readiness bundle" in data["error"]
            assert "local_pro_stack" in data.get("available_bundles", [])

    @pytest.mark.asyncio
    async def test_credentials_readiness_local_pro_stack_shape_and_counts(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        app = self._make_app()
        monkeypatch.setattr("framework.credentials.validation.ensure_credential_key_env", lambda: None)
        for var_name in [
            "BRAVE_SEARCH_API_KEY",
            "GITHUB_TOKEN",
            "TELEGRAM_BOT_TOKEN",
            "GOOGLE_ACCESS_TOKEN",
            "REDIS_URL",
            "DATABASE_URL",
            "GOOGLE_MAPS_API_KEY",
            "GOOGLE_SEARCH_CONSOLE_TOKEN",
            "GOOGLE_APPLICATION_CREDENTIALS",
        ]:
            monkeypatch.delenv(var_name, raising=False)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/credentials/readiness?bundle=local_pro_stack")
            assert resp.status == 200
            data = await resp.json()
            assert data["bundle"] == "local_pro_stack"
            assert len(data.get("required", [])) == 6
            assert len(data.get("optional", [])) == 3
            summary = data.get("summary", {})
            assert summary.get("required_total") == 6
            assert summary.get("required_missing") == 6
            assert summary.get("optional_total") == 3
            assert summary.get("optional_missing") == 3
            assert summary.get("ready") is False
            assert len((data.get("missing") or {}).get("required", [])) == 6
            assert isinstance(data.get("providers"), list)
            assert any(
                isinstance(row, dict) and row.get("provider") == "github"
                for row in data.get("providers", [])
            )


class TestSSEFormat:
    """Tests for SSE event wire format -- events must be unnamed (data-only)
    so the frontend's es.onmessage handler receives them."""

    @pytest.mark.asyncio
    async def test_send_event_without_event_field(self):
        """SSE events without event= should NOT include 'event:' line."""
        from framework.server.sse import SSEResponse

        sse = SSEResponse()
        mock_response = MagicMock()
        mock_response.write = AsyncMock()
        sse._response = mock_response

        await sse.send_event({"type": "client_output_delta", "data": {"content": "hello"}})

        written = mock_response.write.call_args[0][0].decode()
        assert "event:" not in written
        assert "data:" in written
        assert "client_output_delta" in written

    @pytest.mark.asyncio
    async def test_send_event_with_event_field_present(self):
        """Passing event= produces 'event:' line (documents named event behavior)."""
        from framework.server.sse import SSEResponse

        sse = SSEResponse()
        mock_response = MagicMock()
        mock_response.write = AsyncMock()
        sse._response = mock_response

        await sse.send_event({"type": "test"}, event="test")

        written = mock_response.write.call_args[0][0].decode()
        assert "event: test" in written

    def test_events_route_does_not_pass_event_param(self):
        """Guardrail: routes_events.py must call send_event(data) without event=."""
        import inspect

        from framework.server import routes_events

        source = inspect.getsource(routes_events.handle_events)
        # Should NOT contain send_event(data, event=...)
        assert "send_event(data," not in source
        # Should contain the simple call
        assert "send_event(data)" in source


class TestErrorMiddleware:
    @pytest.mark.asyncio
    async def test_unknown_api_route_falls_back_to_frontend(self):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/nonexistent")
            assert resp.status == 200


class TestAutonomousPipeline:
    @pytest.mark.asyncio
    async def test_backlog_create_ci_first_contract_with_service_matrix(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous CI Contract")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Multi-container integration",
                    "goal": "Validate via CI checks for db+cache stack",
                    "acceptance_criteria": ["integration checks green"],
                    "repository": "acme/app",
                    "branch": "main",
                    "required_checks": ["ci/test", "ci/integration"],
                    "workflow": "ci.yaml",
                    "service_matrix": ["postgres", "redis"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()
            assert task["required_checks"] == ["ci/test", "ci/integration"]
            assert task["workflow"] == "ci.yaml"
            assert task["service_matrix"] == ["postgres", "redis"]
            assert task["validation_mode"] == "ci_first"
            assert task["validation_reason"] == "service_matrix_declared"

    @pytest.mark.asyncio
    async def test_backlog_create_defaults_to_ci_first_when_docker_lane_disabled(self, monkeypatch):
        monkeypatch.setenv("HIVE_AUTONOMOUS_DOCKER_LANE_ENABLED", "0")
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Docker Lane Disabled")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Docker lane disabled default",
                    "goal": "Resolver should remain CI-first by default",
                    "acceptance_criteria": ["safe default validation mode"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()
            assert task["validation_mode"] == "ci_first"
            assert task["validation_reason"] == "docker_lane_disabled"

    @pytest.mark.asyncio
    async def test_backlog_update_validation_contract_and_mode_override(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Contract Update")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Contract update",
                    "goal": "Update validation contract",
                    "acceptance_criteria": ["contract updated"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()
            task_id = task["id"]

            update_resp = await client.patch(
                f"/api/projects/{pid}/autonomous/backlog/{task_id}",
                json={
                    "service_matrix": ["postgres"],
                    "required_checks": ["ci/test"],
                },
            )
            assert update_resp.status == 200
            updated = await update_resp.json()
            assert updated["service_matrix"] == ["postgres"]
            assert updated["required_checks"] == ["ci/test"]
            assert updated["validation_mode"] == "ci_first"
            assert updated["validation_reason"] == "service_matrix_declared"

            override_resp = await client.patch(
                f"/api/projects/{pid}/autonomous/backlog/{task_id}",
                json={"validation_mode": "local_or_ci"},
            )
            assert override_resp.status == 200
            overridden = await override_resp.json()
            assert overridden["validation_mode"] == "local_or_ci"
            assert overridden["validation_reason"] == "explicit_request"

    @pytest.mark.asyncio
    async def test_backlog_and_pipeline_happy_path(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Happy")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Implement feature A",
                    "goal": "Ship feature A with tests",
                    "acceptance_criteria": ["tests pass", "docs updated"],
                    "priority": "high",
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()
            task_id = task["id"]

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task_id, "auto_start": True},
            )
            assert run_resp.status == 201
            run = await run_resp.json()
            run_id = run["id"]
            assert run["status"] == "in_progress"
            assert run["current_stage"] == "execution"

            for stage in ("execution", "review", "validation"):
                adv = await client.post(
                    f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                    json={"stage": stage, "result": "success", "notes": f"{stage} ok"},
                )
                assert adv.status == 200

            final_run = await client.get(f"/api/projects/{pid}/autonomous/runs/{run_id}")
            assert final_run.status == 200
            final_data = await final_run.json()
            assert final_data["status"] == "completed"
            assert final_data["stage_states"]["validation"] == "completed"

            tasks_list = await client.get(f"/api/projects/{pid}/autonomous/backlog")
            assert tasks_list.status == 200
            tasks_data = await tasks_list.json()
            by_id = {item["id"]: item for item in tasks_data["tasks"]}
            assert by_id[task_id]["status"] == "done"

    @pytest.mark.asyncio
    async def test_pipeline_escalates_on_review_after_retries(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(
            name="Autonomous Escalation",
            execution_template={
                "retry_policy": {
                    "max_retries_per_stage": 1,
                    "escalate_on": ["review"],
                }
            },
        )
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Bugfix B",
                    "goal": "Fix regression B",
                    "acceptance_criteria": ["bug fixed"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()
            task_id = task["id"]

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task_id, "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            ok_execution = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )
            assert ok_execution.status == 200

            retry_review = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "review", "result": "failed", "notes": "first fail"},
            )
            assert retry_review.status == 200
            retry_data = await retry_review.json()
            assert retry_data["stage_states"]["review"] == "retry_pending"
            assert retry_data["status"] == "in_progress"

            escalated_review = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "review", "result": "failed", "notes": "second fail"},
            )
            assert escalated_review.status == 200
            escalated_data = await escalated_review.json()
            assert escalated_data["status"] == "escalated"
            assert escalated_data["stage_states"]["review"] == "escalated"

            tasks_list = await client.get(f"/api/projects/{pid}/autonomous/backlog")
            tasks_data = await tasks_list.json()
            by_id = {item["id"]: item for item in tasks_data["tasks"]}
            assert by_id[task_id]["status"] == "blocked"

    @pytest.mark.asyncio
    async def test_pipeline_run_create_with_session_triggers_execution(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Session Trigger")
        pid = created["id"]

        session = MagicMock()
        session.id = "session_auto_001"
        session.project_id = pid
        session.graph_runtime = MagicMock()
        session.graph_runtime.trigger = AsyncMock(return_value="exec_auto_001")
        manager._sessions[session.id] = session

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Task with session",
                    "goal": "Execute through live session",
                    "acceptance_criteria": ["execution started"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={
                    "task_id": task["id"],
                    "auto_start": True,
                    "session_id": session.id,
                },
            )
            assert run_resp.status == 201
            run = await run_resp.json()
            assert run["status"] == "in_progress"
            assert run["stage_states"]["execution"] == "running"
            assert run["artifacts"]["stages"]["execution"]["output"]["execution_id"] == "exec_auto_001"

            session.graph_runtime.trigger.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_backlog_create_defaults_repo_and_branch_from_project(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(
            name="Autonomous Backlog Project Defaults",
            repository="github.com/acme/payments-core",
            execution_template={"github": {"default_ref": "develop"}},
        )
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Task defaults",
                    "goal": "Use project-level repo/ref defaults",
                    "acceptance_criteria": ["defaults applied"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()
            assert task["repository"] == "github.com/acme/payments-core"
            assert task["branch"] == "develop"

    @pytest.mark.asyncio
    async def test_pipeline_dispatch_next_picks_highest_priority_todo(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Dispatch Next")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            low_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Low task",
                    "goal": "Run later",
                    "acceptance_criteria": ["ok"],
                    "priority": "low",
                },
            )
            assert low_resp.status == 201
            low_task = await low_resp.json()

            high_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "High task",
                    "goal": "Run first",
                    "acceptance_criteria": ["ok"],
                    "priority": "high",
                },
            )
            assert high_resp.status == 201
            high_task = await high_resp.json()

            dispatch = await client.post(
                f"/api/projects/{pid}/autonomous/dispatch-next",
                json={"auto_start": True},
            )
            assert dispatch.status == 201
            payload = await dispatch.json()
            assert payload["selected_task"]["id"] == high_task["id"]
            assert payload["run"]["task_id"] == high_task["id"]
            assert payload["run"]["status"] == "in_progress"

            tasks = await client.get(f"/api/projects/{pid}/autonomous/backlog")
            tasks_data = await tasks.json()
            by_id = {item["id"]: item for item in tasks_data["tasks"]}
            assert by_id[high_task["id"]]["status"] == "in_progress"
            assert by_id[low_task["id"]]["status"] == "todo"

    @pytest.mark.asyncio
    async def test_pipeline_dispatch_next_rejects_when_active_run_exists(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Dispatch Reject")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Task A",
                    "goal": "Create active run",
                    "acceptance_criteria": ["ok"],
                },
            )
            task = await task_resp.json()
            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            assert run_resp.status == 201
            active_run = await run_resp.json()

            second_task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Task B",
                    "goal": "Should not dispatch while active run exists",
                    "acceptance_criteria": ["ok"],
                    "priority": "critical",
                },
            )
            assert second_task_resp.status == 201

            dispatch = await client.post(
                f"/api/projects/{pid}/autonomous/dispatch-next",
                json={"auto_start": True},
            )
            assert dispatch.status == 409
            err = await dispatch.json()
            assert err["active_run_id"] == active_run["id"]

    @pytest.mark.asyncio
    async def test_pipeline_loop_tick_dispatches_next_when_idle(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Loop Tick Idle")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Loop tick task",
                    "goal": "Dispatch on idle",
                    "acceptance_criteria": ["run created"],
                    "priority": "high",
                },
            )
            assert task_resp.status == 201

            tick = await client.post(
                f"/api/projects/{pid}/autonomous/loop/tick",
                json={"auto_start": True},
            )
            assert tick.status == 201
            payload = await tick.json()
            assert payload["action"] == "dispatched_next_task"
            assert payload["run"]["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_pipeline_loop_tick_returns_await_execution_for_active_execution_run(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Loop Tick Execution")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Execution wait task",
                    "goal": "Stay on execution until result",
                    "acceptance_criteria": ["awaited"],
                },
            )
            task = await task_resp.json()
            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            assert run_resp.status == 201

            tick = await client.post(
                f"/api/projects/{pid}/autonomous/loop/tick",
                json={},
            )
            assert tick.status == 202
            payload = await tick.json()
            assert payload["action"] == "await_execution_stage_result"

    @pytest.mark.asyncio
    async def test_pipeline_loop_tick_updates_execution_heartbeat_while_running(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Loop Tick Heartbeat")
        pid = created["id"]

        from framework.server import routes_autonomous

        def _fake_resolve_execution_outcome(_manager, _run):
            return {
                "status": "running",
                "execution_id": "exec-running-1",
                "session_id": "session-running-1",
                "worker_graph_id": "worker-graph-1",
            }

        monkeypatch.setattr(routes_autonomous, "_resolve_execution_outcome", _fake_resolve_execution_outcome)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Execution heartbeat task",
                    "goal": "Refresh run heartbeat while execution is running",
                    "acceptance_criteria": ["execution stage stays running with fresh artifact"],
                },
            )
            task = await task_resp.json()
            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            assert run_resp.status == 201
            run = await run_resp.json()

            tick = await client.post(
                f"/api/projects/{pid}/autonomous/loop/tick",
                json={},
            )
            assert tick.status == 202
            payload = await tick.json()
            assert payload["action"] == "await_execution_stage_result"
            assert payload["run"]["stage_states"]["execution"] == "running"
            execution_stage = payload["run"]["artifacts"]["stages"]["execution"]
            assert execution_stage["result"] == "running"
            assert execution_stage["source"] == "execution_event_poll"
            assert execution_stage["output"]["execution"]["status"] == "running"
            assert payload["run"]["id"] == run["id"]

    @pytest.mark.asyncio
    async def test_pipeline_loop_tick_all_endpoint(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Tick All")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Tick all task",
                    "goal": "Dispatch from global tick",
                    "acceptance_criteria": ["run created"],
                    "priority": "critical",
                },
            )
            assert task_resp.status == 201

            tick_all = await client.post(
                "/api/autonomous/loop/tick-all",
                json={"project_ids": [pid], "auto_start": True},
            )
            assert tick_all.status == 200
            payload = await tick_all.json()
            assert payload["status"] in {"ok", "partial"}
            assert payload["summary"]["projects_total"] == 1
            assert len(payload["results"]) == 1
            row = payload["results"][0]
            assert row["project_id"] == pid
            assert row["status"] in {200, 201, 202}
            assert row.get("action") in {
                "dispatched_next_task",
                "await_execution_stage_result",
                "execution_stage_resolved",
                "await_manual_stage_resolution",
                "advanced_with_github_checks",
                "idle_no_todo_tasks",
                "manual_evaluate_required",
            }

    @pytest.mark.asyncio
    async def test_pipeline_loop_tick_all_rejects_non_array_project_ids(self):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            tick_all = await client.post(
                "/api/autonomous/loop/tick-all",
                json={"project_ids": "default"},
            )
            assert tick_all.status == 400

    @pytest.mark.asyncio
    async def test_pipeline_loop_run_cycle_endpoint(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Run Cycle")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Run cycle task",
                    "goal": "Advance with multi-step loop",
                    "acceptance_criteria": ["cycle returns steps"],
                    "priority": "high",
                },
            )
            assert task_resp.status == 201

            cycle = await client.post(
                "/api/autonomous/loop/run-cycle",
                json={"project_ids": [pid], "auto_start": False, "max_steps_per_project": 3},
            )
            assert cycle.status == 200
            payload = await cycle.json()
            assert payload["status"] in {"ok", "partial"}
            assert payload["summary"]["projects_total"] == 1
            row = payload["results"][0]
            assert row["project_id"] == pid
            assert row["steps_executed"] >= 1
            assert isinstance(row["steps"], list)
            assert row["status"] in {200, 201, 202, 400, 409}

    @pytest.mark.asyncio
    async def test_pipeline_loop_run_cycle_rejects_invalid_max_steps(self):
        app = create_app()
        async with TestClient(TestServer(app)) as client:
            bad = await client.post(
                "/api/autonomous/loop/run-cycle",
                json={"max_steps_per_project": 0},
            )
            assert bad.status == 400

            bad2 = await client.post(
                "/api/autonomous/loop/run-cycle",
                json={"max_steps_per_project": "x"},
            )
            assert bad2.status == 400

    @pytest.mark.asyncio
    async def test_pipeline_loop_run_cycle_reports_terminal_and_pr_ready(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Run Cycle Terminal")
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        from framework.server import routes_autonomous

        def _fake_resolve(*, token, repository, ref, pr_url):
            assert token == "test-token"
            return repository or "acme/repo", ref or "main"

        def _fake_fetch(*, repository, ref, token, required_checks=None):
            return {
                "repository": repository,
                "ref": ref,
                "checks": [{"name": "checks", "passed": True, "severity": "error", "details": ""}],
                "checks_summary": {"total": 1, "passed": 1, "failed": 0, "all_passed": True, "failures": []},
                "sha": "abc123",
            }

        monkeypatch.setattr(routes_autonomous, "_resolve_github_target", _fake_resolve)
        monkeypatch.setattr(routes_autonomous, "_fetch_github_checks", _fake_fetch)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Run cycle terminal",
                    "goal": "Reach completed via run-cycle",
                    "acceptance_criteria": ["terminal summary present"],
                    "repository": "acme/repo",
                    "branch": "main",
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )

            cycle = await client.post(
                "/api/autonomous/loop/run-cycle",
                json={
                    "project_ids": [pid],
                    "max_steps_per_project": 3,
                    "repository": "acme/repo",
                    "ref": "main",
                    "pr_url": "https://github.com/acme/repo/pull/42",
                },
            )
            assert cycle.status == 200
            payload = await cycle.json()
            row = payload["results"][0]
            assert row["terminal"] is True
            assert row["terminal_status"] == "completed"
            assert row["terminal_run_id"] == run_id
            assert row["pr_ready"] is True

    @pytest.mark.asyncio
    async def test_pipeline_loop_run_cycle_summary_outcomes(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Run Cycle Outcomes")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            tick = await client.post(
                "/api/autonomous/loop/run-cycle",
                json={"project_ids": [pid], "auto_start": False, "max_steps_per_project": 1},
            )
            assert tick.status == 200
            payload = await tick.json()
            assert payload["summary"]["projects_total"] == 1
            outcomes = payload["summary"].get("outcomes") or {}
            assert isinstance(outcomes, dict)
            assert outcomes.get("idle", 0) >= 1
            row = payload["results"][0]
            assert row.get("outcome") == "idle"

    @pytest.mark.asyncio
    async def test_pipeline_loop_run_cycle_report_endpoint(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Run Cycle Report")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            report_resp = await client.post(
                "/api/autonomous/loop/run-cycle/report",
                json={"project_ids": [pid], "auto_start": False, "max_steps_per_project": 1},
            )
            assert report_resp.status == 200
            payload = await report_resp.json()
            assert payload["status"] in {"ok", "partial"}
            assert "summary" in payload
            assert "projects" in payload
            assert "highlights" in payload
            assert payload["summary"]["projects_total"] == 1
            assert isinstance(payload["summary"].get("outcomes"), dict)
            assert isinstance(payload["projects"], list)
            assert len(payload["projects"]) == 1
            first = payload["projects"][0]
            assert first["project_id"] == pid
            assert "outcome" in first

    @pytest.mark.asyncio
    async def test_pipeline_loop_tick_resolves_execution_completed_from_event_log(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Loop Tick Completed")
        pid = created["id"]

        session = _make_session(agent_id="session_exec_done")
        session.project_id = pid
        session.graph_runtime.trigger = AsyncMock(return_value="exec_done")
        manager._sessions[session.id] = session

        events_dir = tmp_path / ".hive" / "queen" / "session" / session.id
        events_dir.mkdir(parents=True, exist_ok=True)
        (events_dir / "events.jsonl").write_text(
            json.dumps({"type": "execution_completed", "execution_id": "exec_done"}) + "\n",
            encoding="utf-8",
        )

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Execution complete task",
                    "goal": "Auto-advance by event log",
                    "acceptance_criteria": ["moves to review"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True, "session_id": session.id},
            )
            run = await run_resp.json()
            assert run["current_stage"] == "execution"

            tick = await client.post(
                f"/api/projects/{pid}/autonomous/loop/tick",
                json={},
            )
            assert tick.status == 200
            payload = await tick.json()
            assert payload["action"] == "execution_stage_resolved"
            assert payload["run"]["current_stage"] == "review"
            assert payload["run"]["stage_states"]["execution"] == "completed"

    @pytest.mark.asyncio
    async def test_pipeline_loop_tick_ignores_queen_active_stream_when_worker_completed(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Loop Tick Worker Graph Filter")
        pid = created["id"]

        worker_stream = MockStream(active_execution_ids=set())
        queen_stream = MockStream(active_execution_ids={"exec_same_id"})
        worker_reg = MockGraphRegistration(streams={"default": worker_stream})
        queen_reg = MockGraphRegistration(streams={"queen": queen_stream})

        class _RuntimeWithQueenAndWorker(MockRuntime):
            def __init__(self):
                super().__init__()
                self._graph_id = "worker-graph"
                self.trigger = AsyncMock(return_value="exec_same_id")

            def list_graphs(self):
                return ["queen-graph", "worker-graph"]

            def get_graph_registration(self, graph_id):
                if graph_id == "queen-graph":
                    return queen_reg
                if graph_id == "worker-graph":
                    return worker_reg
                return None

        session = _make_session(agent_id="session_exec_graph_filter", runtime=_RuntimeWithQueenAndWorker())
        session.project_id = pid
        manager._sessions[session.id] = session

        events_dir = tmp_path / ".hive" / "queen" / "session" / session.id
        events_dir.mkdir(parents=True, exist_ok=True)
        (events_dir / "events.jsonl").write_text(
            json.dumps(
                {
                    "type": "execution_completed",
                    "execution_id": "exec_same_id",
                    "graph_id": "worker-graph",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Execution complete despite queen stream",
                    "goal": "Resolve by worker event only",
                    "acceptance_criteria": ["moves to review"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True, "session_id": session.id},
            )
            run = await run_resp.json()
            assert run["current_stage"] == "execution"

            tick = await client.post(
                f"/api/projects/{pid}/autonomous/loop/tick",
                json={},
            )
            assert tick.status == 200
            payload = await tick.json()
            assert payload["action"] == "execution_stage_resolved"
            assert payload["run"]["current_stage"] == "review"
            assert payload["run"]["stage_states"]["execution"] == "completed"

    @pytest.mark.asyncio
    async def test_pipeline_loop_tick_resolves_when_terminal_worker_completed_without_execution_event(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Loop Tick Terminal Worker Fallback")
        pid = created["id"]

        worker_stream = MockStream(active_execution_ids={"exec_same_id"})
        worker_graph = MockGraphSpec()
        worker_graph.terminal_nodes = ("report",)
        worker_reg = MockGraphRegistration(graph=worker_graph, streams={"default": worker_stream})

        class _RuntimeWithStaleActiveId(MockRuntime):
            def __init__(self):
                super().__init__()
                self._graph_id = "worker-graph"
                self.trigger = AsyncMock(return_value="exec_same_id")

            def list_graphs(self):
                return ["worker-graph"]

            def get_graph_registration(self, graph_id):
                if graph_id == "worker-graph":
                    return worker_reg
                return None

        session = _make_session(agent_id="session_exec_terminal_worker", runtime=_RuntimeWithStaleActiveId())
        session.project_id = pid
        manager._sessions[session.id] = session

        events_dir = tmp_path / ".hive" / "queen" / "session" / session.id
        events_dir.mkdir(parents=True, exist_ok=True)
        (events_dir / "events.jsonl").write_text(
            json.dumps(
                {
                    "type": "worker_completed",
                    "execution_id": "exec_same_id",
                    "graph_id": "worker-graph",
                    "data": {"worker_id": "report", "success": True},
                }
            )
            + "\n",
            encoding="utf-8",
        )

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Terminal worker fallback",
                    "goal": "Resolve when worker terminal event exists",
                    "acceptance_criteria": ["moves to review"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True, "session_id": session.id},
            )
            run = await run_resp.json()
            assert run["current_stage"] == "execution"

            tick = await client.post(
                f"/api/projects/{pid}/autonomous/loop/tick",
                json={},
            )
            assert tick.status == 200
            payload = await tick.json()
            assert payload["action"] == "execution_stage_resolved"
            assert payload["run"]["current_stage"] == "review"
            assert payload["run"]["stage_states"]["execution"] == "completed"

    @pytest.mark.asyncio
    async def test_pipeline_loop_tick_resolves_from_worker_completed_when_session_not_loaded(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Loop Tick Cold Restart Worker Fallback")
        pid = created["id"]

        # Intentionally do not register session in manager._sessions to simulate
        # a restart where execution events exist on disk but live session is absent.
        session_id = "session_exec_cold_restart"

        events_dir = tmp_path / ".hive" / "queen" / "session" / session_id
        events_dir.mkdir(parents=True, exist_ok=True)
        (events_dir / "events.jsonl").write_text(
            json.dumps(
                {
                    "type": "worker_completed",
                    "execution_id": "exec_cold_restart",
                    "graph_id": "worker-graph",
                    "data": {
                        "worker_id": "report",
                        "success": True,
                        "activations": [],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Cold restart worker fallback",
                    "goal": "Resolve execution without live session object",
                    "acceptance_criteria": ["moves to review"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            # Emulate already-running execution artifact created before restart.
            from framework.server.routes_autonomous import APP_KEY_AUTONOMOUS_STORE

            store = app[APP_KEY_AUTONOMOUS_STORE]
            run_obj = store.get_run(run_id)
            assert run_obj is not None
            artifacts = dict(run_obj.artifacts)
            stages = dict(artifacts.get("stages", {}))
            stages["execution"] = {
                "result": "running",
                "timestamp": time.time(),
                "output": {
                    "execution_id": "exec_cold_restart",
                    "session_id": session_id,
                    "worker_graph_id": "worker-graph",
                },
                "attempt": 1,
            }
            artifacts["stages"] = stages
            updated = store.update_run(
                run_id,
                {
                    "status": "in_progress",
                    "current_stage": "execution",
                    "stage_states": {
                        "execution": "running",
                        "review": "pending",
                        "validation": "pending",
                    },
                    "artifacts": artifacts,
                },
            )
            assert updated is not None

            tick = await client.post(
                f"/api/projects/{pid}/autonomous/loop/tick",
                json={},
            )
            assert tick.status == 200
            payload = await tick.json()
            assert payload["action"] == "execution_stage_resolved"
            assert payload["run"]["current_stage"] == "review"
            assert payload["run"]["stage_states"]["execution"] == "completed"

    @pytest.mark.asyncio
    async def test_pipeline_loop_tick_resolves_execution_failed_from_event_log(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(
            name="Autonomous Loop Tick Failed",
            execution_template={"retry_policy": {"max_retries_per_stage": 0, "escalate_on": []}},
        )
        pid = created["id"]

        session = _make_session(agent_id="session_exec_fail")
        session.project_id = pid
        session.graph_runtime.trigger = AsyncMock(return_value="exec_fail")
        manager._sessions[session.id] = session

        events_dir = tmp_path / ".hive" / "queen" / "session" / session.id
        events_dir.mkdir(parents=True, exist_ok=True)
        (events_dir / "events.jsonl").write_text(
            json.dumps({"type": "execution_failed", "execution_id": "exec_fail"}) + "\n",
            encoding="utf-8",
        )

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Execution fail task",
                    "goal": "Auto-fail by event log",
                    "acceptance_criteria": ["marks blocked"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True, "session_id": session.id},
            )
            run = await run_resp.json()
            assert run["current_stage"] == "execution"

            tick = await client.post(
                f"/api/projects/{pid}/autonomous/loop/tick",
                json={},
            )
            assert tick.status == 200
            payload = await tick.json()
            assert payload["action"] == "execution_stage_resolved"
            assert payload["run"]["status"] == "failed"
            assert payload["run"]["stage_states"]["execution"] == "failed"

            tasks_list = await client.get(f"/api/projects/{pid}/autonomous/backlog")
            tasks_data = await tasks_list.json()
            by_id = {item["id"]: item for item in tasks_data["tasks"]}
            assert by_id[task["id"]]["status"] == "blocked"

    @pytest.mark.asyncio
    async def test_pipeline_report_endpoint(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Report")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Report task",
                    "goal": "Generate final report",
                    "acceptance_criteria": ["report available"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            for stage in ("execution", "review", "validation"):
                adv = await client.post(
                    f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                    json={"stage": stage, "result": "success", "summary": "all good"},
                )
                assert adv.status == 200

            report_resp = await client.get(f"/api/projects/{pid}/autonomous/runs/{run_id}/report")
            assert report_resp.status == 200
            report = await report_resp.json()
            assert report["run_id"] == run_id
            assert report["status"] == "completed"
            assert report["report"]["final_status"] == "completed"

    @pytest.mark.asyncio
    async def test_pipeline_evaluate_endpoint_uses_checks_and_updates_report(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Evaluate")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Evaluate task",
                    "goal": "Auto-evaluate review stage",
                    "acceptance_criteria": ["checks pass"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )

            eval_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/evaluate",
                json={
                    "stage": "review",
                    "source": "ci_checks",
                    "checks": [
                        {"name": "lint", "passed": True},
                        {"name": "tests", "passed": True},
                    ],
                    "notes": "review checks green",
                },
            )
            assert eval_resp.status == 200
            eval_data = await eval_resp.json()
            assert eval_data["current_stage"] == "validation"
            assert eval_data["stage_states"]["review"] == "completed"

            report_resp = await client.get(f"/api/projects/{pid}/autonomous/runs/{run_id}/report")
            report = await report_resp.json()
            assert report["report"]["checks"]["review"]["all_passed"] is True
            assert report["report"]["task"]["task_id"] == task["id"]

    @pytest.mark.asyncio
    async def test_pipeline_evaluate_endpoint_accepts_status_field(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Evaluate Status Alias")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Evaluate task status alias",
                    "goal": "Auto-evaluate review stage via status field",
                    "acceptance_criteria": ["checks pass"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )

            eval_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/evaluate",
                json={
                    "stage": "review",
                    "checks": [
                        {"name": "lint", "status": "passed"},
                        {"name": "tests", "status": "success"},
                    ],
                },
            )
            assert eval_resp.status == 200
            eval_data = await eval_resp.json()
            assert eval_data["current_stage"] == "validation"
            assert eval_data["stage_states"]["review"] == "completed"

            report_resp = await client.get(f"/api/projects/{pid}/autonomous/runs/{run_id}/report")
            report = await report_resp.json()
            review_checks = report["report"]["checks"]["review"]
            assert review_checks["all_passed"] is True
            assert review_checks["passed"] == 2

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_endpoint(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Ops")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Ops task",
                    "goal": "Have state to aggregate",
                    "acceptance_criteria": ["visible in ops status"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            assert run_resp.status == 201

            status_resp = await client.get("/api/autonomous/ops/status")
            assert status_resp.status == 200
            status_data = await status_resp.json()
            assert status_data["status"] == "ok"
            assert status_data["summary"]["tasks_total"] >= 1
            assert status_data["summary"]["runs_total"] >= 1
            assert pid in status_data["projects"]

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_reports_docker_lane_disabled(self, monkeypatch):
        monkeypatch.setenv("HIVE_AUTONOMOUS_DOCKER_LANE_ENABLED", "0")
        app = create_app()

        async with TestClient(TestServer(app)) as client:
            status_resp = await client.get("/api/autonomous/ops/status")
            assert status_resp.status == 200
            payload = await status_resp.json()

            lane = payload["runtime"]["docker_lane"]
            assert lane["enabled"] is False
            assert lane["status"] == "disabled"
            assert lane["reason"] == "feature_flag_disabled"
            assert payload["summary"]["docker_lane_enabled"] is False
            assert payload["summary"]["docker_lane_ready"] is False

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_reports_docker_lane_ready(self, monkeypatch):
        monkeypatch.setenv("HIVE_AUTONOMOUS_DOCKER_LANE_ENABLED", "1")
        app = create_app()

        from framework.server import routes_autonomous

        monkeypatch.setattr(
            routes_autonomous.shutil,
            "which",
            lambda cmd: "/usr/bin/docker" if cmd == "docker" else None,
        )

        class _Result:
            returncode = 0
            stdout = '"26.1.0"\n'
            stderr = ""

        def _fake_run(*args, **kwargs):
            return _Result()

        monkeypatch.setattr(routes_autonomous.subprocess, "run", _fake_run)

        async with TestClient(TestServer(app)) as client:
            status_resp = await client.get("/api/autonomous/ops/status")
            assert status_resp.status == 200
            payload = await status_resp.json()

            lane = payload["runtime"]["docker_lane"]
            assert lane["enabled"] is True
            assert lane["ready"] is True
            assert lane["status"] == "ready"
            assert lane["reason"] == "ok"
            assert lane["server_version"] == "26.1.0"
            assert payload["summary"]["docker_lane_enabled"] is True
            assert payload["summary"]["docker_lane_ready"] is True

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_reports_docker_lane_degraded(self, monkeypatch):
        monkeypatch.setenv("HIVE_AUTONOMOUS_DOCKER_LANE_ENABLED", "1")
        app = create_app()

        from framework.server import routes_autonomous

        monkeypatch.setattr(
            routes_autonomous.shutil,
            "which",
            lambda cmd: "/usr/bin/docker" if cmd == "docker" else None,
        )

        class _Result:
            returncode = 1
            stdout = ""
            stderr = "Cannot connect to the Docker daemon"

        def _fake_run(*args, **kwargs):
            return _Result()

        monkeypatch.setattr(routes_autonomous.subprocess, "run", _fake_run)

        async with TestClient(TestServer(app)) as client:
            status_resp = await client.get("/api/autonomous/ops/status")
            assert status_resp.status == 200
            payload = await status_resp.json()

            lane = payload["runtime"]["docker_lane"]
            assert lane["enabled"] is True
            assert lane["ready"] is False
            assert lane["status"] == "degraded"
            assert lane["reason"] == "docker_daemon_unreachable"
            assert payload["summary"]["docker_lane_enabled"] is True
            assert payload["summary"]["docker_lane_ready"] is False

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_reports_stuck_runs(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Ops Stuck")
        pid = created["id"]
        monkeypatch.setenv("HIVE_AUTONOMOUS_STUCK_RUN_SECONDS", "120")
        monkeypatch.setenv("HIVE_AUTONOMOUS_NO_PROGRESS_SECONDS", "120")

        from framework.server import routes_autonomous

        base_ts = 1_700_000_000.0
        monkeypatch.setattr(routes_autonomous.time, "time", lambda: base_ts)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Ops stuck task",
                    "goal": "Create stale in-progress run",
                    "acceptance_criteria": ["visible in stuck alert"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            assert run_resp.status == 201
            run = await run_resp.json()

            monkeypatch.setattr(routes_autonomous.time, "time", lambda: base_ts + 600.0)

            status_resp = await client.get("/api/autonomous/ops/status")
            assert status_resp.status == 200
            status_data = await status_resp.json()
            assert status_data["status"] == "ok"
            alerts = status_data["alerts"]
            assert alerts["stuck_threshold_seconds"] == 120
            assert alerts["stuck_runs_total"] >= 1
            assert any(item["run_id"] == run["id"] for item in alerts["stuck_runs"])
            assert alerts["no_progress_threshold_seconds"] >= 60
            assert alerts["no_progress_projects_total"] >= 1
            assert any(item["project_id"] == pid for item in alerts["no_progress_projects"])
            assert status_data["projects"][pid]["stuck_runs"] >= 1

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_ignores_orphaned_pipeline_state_by_default(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        manager.create_project(name="Active project")
        store = app[APP_KEY_AUTONOMOUS_STORE]

        orphan_project_id = "orphan-project-state"
        orphan_task = store.create_task(
            project_id=orphan_project_id,
            title="Orphan task",
            goal="Verify orphan filtering in ops status",
            acceptance_criteria=["not counted by default"],
        )
        store.create_run(project_id=orphan_project_id, task_id=orphan_task.id)

        async with TestClient(TestServer(app)) as client:
            default_resp = await client.get("/api/autonomous/ops/status")
            assert default_resp.status == 200
            default_payload = await default_resp.json()
            assert default_payload["summary"]["include_orphaned"] is False
            assert default_payload["summary"]["orphaned_tasks_total"] >= 1
            assert default_payload["summary"]["orphaned_runs_total"] >= 1
            assert orphan_project_id not in default_payload["projects"]

            include_resp = await client.get("/api/autonomous/ops/status?include_orphaned=1")
            assert include_resp.status == 200
            include_payload = await include_resp.json()
            assert include_payload["summary"]["include_orphaned"] is True
            assert include_payload["summary"]["tasks_total"] >= default_payload["summary"]["tasks_total"] + 1
            assert include_payload["summary"]["runs_total"] >= default_payload["summary"]["runs_total"] + 1
            assert orphan_project_id in include_payload["projects"]

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_filters_by_project_id(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        p1 = manager.create_project(name="Autonomous Ops Filter A")["id"]
        p2 = manager.create_project(name="Autonomous Ops Filter B")["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{p1}/autonomous/backlog",
                json={
                    "title": "P1 task",
                    "goal": "Project filter baseline",
                    "acceptance_criteria": ["present in filtered summary"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()
            run_resp = await client.post(
                f"/api/projects/{p1}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            assert run_resp.status == 201

            task_resp_p2 = await client.post(
                f"/api/projects/{p2}/autonomous/backlog",
                json={
                    "title": "P2 task",
                    "goal": "Noise project",
                    "acceptance_criteria": ["must be filtered out"],
                },
            )
            assert task_resp_p2.status == 201

            status_resp = await client.get(f"/api/autonomous/ops/status?project_id={p1}")
            assert status_resp.status == 200
            payload = await status_resp.json()

            assert payload["summary"]["project_filter"] == p1
            assert payload["summary"]["tasks_total"] >= 1
            assert p1 in payload["projects"]
            assert p2 not in payload["projects"]

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_reports_no_progress_projects(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        pid = manager.create_project(name="Autonomous Ops No Progress")["id"]
        monkeypatch.setenv("HIVE_AUTONOMOUS_NO_PROGRESS_SECONDS", "120")

        from framework.server import routes_autonomous

        base_ts = 1_701_000_000.0
        monkeypatch.setattr(routes_autonomous.time, "time", lambda: base_ts)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "No progress task",
                    "goal": "Create active run with stale updates",
                    "acceptance_criteria": ["visible in no-progress alert"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()
            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            assert run_resp.status == 201

            monkeypatch.setattr(routes_autonomous.time, "time", lambda: base_ts + 240.0)
            status_resp = await client.get("/api/autonomous/ops/status")
            assert status_resp.status == 200
            payload = await status_resp.json()
            alerts = payload["alerts"]

            assert alerts["no_progress_threshold_seconds"] == 120
            assert alerts["no_progress_projects_total"] >= 1
            project_rows = [item for item in alerts["no_progress_projects"] if item["project_id"] == pid]
            assert project_rows
            assert project_rows[0]["active_runs"] >= 1
            assert project_rows[0]["max_no_progress_seconds"] >= 240.0

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_include_runs_details(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        pid = manager.create_project(name="Autonomous Ops Include Runs")["id"]

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Runs details task",
                    "goal": "Ensure include_runs returns active run rows",
                    "acceptance_criteria": ["active run present in response"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()
            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            assert run_resp.status == 201
            run = await run_resp.json()

            status_resp = await client.get(f"/api/autonomous/ops/status?project_id={pid}&include_runs=true")
            assert status_resp.status == 200
            payload = await status_resp.json()

            assert payload["summary"]["include_runs"] is True
            active_runs = payload["active_runs"]
            assert active_runs
            assert any(row["run_id"] == run["id"] for row in active_runs)

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_reads_loop_state_file(self, tmp_path, monkeypatch):
        app = create_app()
        loop_state_path = tmp_path / "autonomous_loop_state.json"
        loop_state_path.write_text(
            json.dumps(
                {
                    "started_at": 1_700_000_000.0,
                    "finished_at": 1_700_000_010.0,
                    "updated_at": 1_700_000_010.0,
                    "status": "ok",
                    "summary": {"ok": 2, "deferred": 0, "failed": 0, "projects_total": 2},
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("HIVE_AUTONOMOUS_LOOP_STATE_PATH", str(loop_state_path))

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/autonomous/ops/status")
            assert resp.status == 200
            payload = await resp.json()

            assert payload["loop"]["state_path"] == str(loop_state_path)
            assert payload["loop"]["state"]["status"] == "ok"
            assert payload["loop"]["state"]["summary"]["ok"] == 2
            assert payload["alerts"]["loop_stale"] in {True, False}

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_reports_stale_loop_state(self, tmp_path, monkeypatch):
        app = create_app()
        loop_state_path = tmp_path / "autonomous_loop_state.json"
        loop_state_path.write_text(
            json.dumps(
                {
                    "started_at": 1_000.0,
                    "updated_at": 1_200.0,
                    "status": "running",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("HIVE_AUTONOMOUS_LOOP_STATE_PATH", str(loop_state_path))
        monkeypatch.setenv("HIVE_AUTONOMOUS_LOOP_STALE_SECONDS", "120")

        from framework.server import routes_autonomous

        monkeypatch.setattr(routes_autonomous.time, "time", lambda: 1_600.0)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/autonomous/ops/status")
            assert resp.status == 200
            payload = await resp.json()

            assert payload["alerts"]["loop_stale_threshold_seconds"] == 120
            assert payload["alerts"]["loop_stale"] is True
            assert payload["alerts"]["loop_stale_seconds"] >= 400.0
            assert payload["loop"]["stale"] is True

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_ignores_stale_terminal_loop_snapshot_without_active_runs(
        self, tmp_path, monkeypatch
    ):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        pid = manager.create_project(name="Autonomous Ops Terminal Loop Snapshot")["id"]
        loop_state_path = tmp_path / "autonomous_loop_state.json"
        loop_state_path.write_text(
            json.dumps(
                {
                    "started_at": 1_000.0,
                    "finished_at": 1_200.0,
                    "updated_at": 1_200.0,
                    "status": "failed",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("HIVE_AUTONOMOUS_LOOP_STATE_PATH", str(loop_state_path))
        monkeypatch.setenv("HIVE_AUTONOMOUS_LOOP_STALE_SECONDS", "120")

        from framework.server import routes_autonomous

        monkeypatch.setattr(routes_autonomous.time, "time", lambda: 1_600.0)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get(f"/api/autonomous/ops/status?project_id={pid}")
            assert resp.status == 200
            payload = await resp.json()

            assert payload["alerts"]["loop_stale_threshold_seconds"] == 120
            assert payload["alerts"]["loop_stale_seconds"] >= 400.0
            assert payload["alerts"]["loop_stale"] is False
            assert payload["loop"]["stale"] is False

    @pytest.mark.asyncio
    async def test_autonomous_ops_status_ignores_stale_terminal_loop_snapshot_with_healthy_active_runs(
        self, tmp_path, monkeypatch
    ):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        pid = manager.create_project(name="Autonomous Ops Healthy Active Runs")["id"]
        loop_state_path = tmp_path / "autonomous_loop_state.json"
        now_ts = 1_700_000_000.0
        loop_state_path.write_text(
            json.dumps(
                {
                    "started_at": now_ts - 1_500.0,
                    "finished_at": now_ts - 1_000.0,
                    "updated_at": now_ts - 1_000.0,
                    "status": "failed",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("HIVE_AUTONOMOUS_LOOP_STATE_PATH", str(loop_state_path))
        monkeypatch.setenv("HIVE_AUTONOMOUS_LOOP_STALE_SECONDS", "120")

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Healthy active run task",
                    "goal": "Ensure stale terminal loop snapshot is ignored without active symptoms",
                    "acceptance_criteria": ["loop stale suppressed when runs are healthy"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()
            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            assert run_resp.status == 201

            from framework.server import routes_autonomous

            monkeypatch.setattr(routes_autonomous.time, "time", lambda: now_ts)

            resp = await client.get(f"/api/autonomous/ops/status?project_id={pid}")
            assert resp.status == 200
            payload = await resp.json()

            assert payload["summary"]["runs_by_status"]["in_progress"] >= 1
            assert payload["alerts"]["stuck_runs_total"] == 0
            assert payload["alerts"]["no_progress_projects_total"] == 0
            assert payload["alerts"]["loop_stale"] is False
            assert payload["loop"]["stale"] is False

    @pytest.mark.asyncio
    async def test_autonomous_ops_remediate_stale_dry_run(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        pid = manager.create_project(name="Autonomous Ops Remediate Dry Run")["id"]

        from framework.server import routes_autonomous

        base_ts = 1_702_000_000.0
        monkeypatch.setattr(routes_autonomous.time, "time", lambda: base_ts)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Stale run",
                    "goal": "Test stale remediation dry-run",
                    "acceptance_criteria": ["detect candidate"],
                },
            )
            task = await task_resp.json()
            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()

            monkeypatch.setattr(routes_autonomous.time, "time", lambda: base_ts + 600.0)
            resp = await client.post(
                "/api/autonomous/ops/remediate-stale",
                json={
                    "dry_run": True,
                    "project_id": pid,
                    "older_than_seconds": 120,
                    "max_runs": 10,
                },
            )
            assert resp.status == 200
            payload = await resp.json()
            assert payload["dry_run"] is True
            assert payload["selected_total"] >= 1
            assert any(row["run_id"] == run["id"] for row in payload["selected"])
            assert payload["remediated_total"] == 0

    @pytest.mark.asyncio
    async def test_autonomous_ops_remediate_stale_apply(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        pid = manager.create_project(name="Autonomous Ops Remediate Apply")["id"]

        from framework.server import routes_autonomous

        base_ts = 1_703_000_000.0
        monkeypatch.setattr(routes_autonomous.time, "time", lambda: base_ts)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Apply stale run",
                    "goal": "Remediate stale run",
                    "acceptance_criteria": ["run moved to terminal"],
                },
            )
            task = await task_resp.json()
            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()

            monkeypatch.setattr(routes_autonomous.time, "time", lambda: base_ts + 720.0)
            remediate_resp = await client.post(
                "/api/autonomous/ops/remediate-stale",
                json={
                    "dry_run": False,
                    "confirm": True,
                    "project_id": pid,
                    "older_than_seconds": 120,
                    "action": "escalated",
                },
            )
            assert remediate_resp.status == 200
            rem = await remediate_resp.json()
            assert rem["remediated_total"] >= 1
            assert any(row["run_id"] == run["id"] for row in rem["remediated"])

            run_get = await client.get(f"/api/projects/{pid}/autonomous/runs/{run['id']}")
            run_payload = await run_get.json()
            assert run_payload["status"] == "escalated"
            assert run_payload["finished_at"] is not None

            backlog = await client.get(f"/api/projects/{pid}/autonomous/backlog")
            backlog_payload = await backlog.json()
            task_rows = [row for row in backlog_payload.get("tasks", []) if row.get("id") == task["id"]]
            assert task_rows
            assert task_rows[0]["status"] == "blocked"

    @pytest.mark.asyncio
    async def test_autonomous_ops_purge_orphaned_dry_run_and_apply(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        store = app[APP_KEY_AUTONOMOUS_STORE]
        manager.create_project(name="Purge Orphaned Active Project")

        orphan_project_id = f"orphan-purge-{int(time.time() * 1000000)}"
        orphan_task = store.create_task(
            project_id=orphan_project_id,
            title="Orphan purge task",
            goal="validate orphan purge endpoint",
            acceptance_criteria=["orphaned state is discoverable and purgeable"],
        )
        store.create_run(project_id=orphan_project_id, task_id=orphan_task.id)

        async with TestClient(TestServer(app)) as client:
            dry_resp = await client.post(
                "/api/autonomous/ops/purge-orphaned",
                json={"dry_run": True},
            )
            assert dry_resp.status == 200
            dry_payload = await dry_resp.json()
            assert dry_payload["status"] == "ok"
            assert dry_payload["dry_run"] is True
            assert dry_payload["orphaned_projects_total"] >= 1
            assert any(row["project_id"] == orphan_project_id for row in dry_payload["selected"])

            denied_resp = await client.post(
                "/api/autonomous/ops/purge-orphaned",
                json={"dry_run": False, "confirm": False},
            )
            assert denied_resp.status == 400

            apply_resp = await client.post(
                "/api/autonomous/ops/purge-orphaned",
                json={"dry_run": False, "confirm": True, "max_projects": 5000},
            )
            assert apply_resp.status == 200
            apply_payload = await apply_resp.json()
            assert apply_payload["status"] == "ok"
            assert apply_payload["dry_run"] is False
            assert any(row["project_id"] == orphan_project_id for row in apply_payload["purged"])
            assert all(t.project_id != orphan_project_id for t in store.list_all_tasks())
            assert all(r.project_id != orphan_project_id for r in store.list_all_runs())

    @pytest.mark.asyncio
    async def test_autonomous_ops_remediate_stale_skips_orphaned_by_default(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        manager.create_project(name="Only Active Project")
        store = app[APP_KEY_AUTONOMOUS_STORE]

        from framework.server import routes_autonomous

        base_ts = 1_704_000_000.0
        monkeypatch.setattr(routes_autonomous.time, "time", lambda: base_ts)
        orphan_project_id = "orphan-remediate-project"
        orphan_task = store.create_task(
            project_id=orphan_project_id,
            title="Orphan stale task",
            goal="Ensure stale remediation skips orphaned projects",
            acceptance_criteria=["not selected unless include_orphaned=true"],
        )
        orphan_run = store.create_run(project_id=orphan_project_id, task_id=orphan_task.id)
        store.update_run(orphan_run.id, {"status": "in_progress"})

        monkeypatch.setattr(routes_autonomous.time, "time", lambda: base_ts + 600.0)

        async with TestClient(TestServer(app)) as client:
            default_resp = await client.post(
                "/api/autonomous/ops/remediate-stale",
                json={"dry_run": True, "older_than_seconds": 120, "max_runs": 10},
            )
            assert default_resp.status == 200
            default_payload = await default_resp.json()
            assert default_payload["include_orphaned"] is False
            assert default_payload["orphaned_skipped_total"] >= 1
            assert not any(row["run_id"] == orphan_run.id for row in default_payload.get("selected", []))

            include_resp = await client.post(
                "/api/autonomous/ops/remediate-stale",
                json={
                    "dry_run": True,
                    "include_orphaned": True,
                    "older_than_seconds": 120,
                    "max_runs": 2000,
                },
            )
            assert include_resp.status == 200
            include_payload = await include_resp.json()
            assert include_payload["include_orphaned"] is True
            assert any(row["run_id"] == orphan_run.id for row in include_payload["selected"])

    @pytest.mark.asyncio
    async def test_pipeline_run_until_terminal_endpoint(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Run Until Terminal")
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        from framework.server import routes_autonomous

        def _fake_resolve_execution_outcome(_manager, _run):
            return {"status": "completed", "reason": "test_completed"}

        def _fake_fetch(*, repository, ref, token, required_checks=None):
            assert repository == "acme/repo"
            assert ref == "main"
            assert token == "test-token"
            return {
                "repository": repository,
                "ref": ref,
                "checks": [
                    {"name": "lint", "passed": True, "severity": "error", "details": ""},
                    {"name": "tests", "passed": True, "severity": "error", "details": ""},
                ],
                "checks_summary": {"total": 2, "passed": 2, "failed": 0, "all_passed": True, "failures": []},
                "sha": "abc123",
            }

        monkeypatch.setattr(routes_autonomous, "_resolve_execution_outcome", _fake_resolve_execution_outcome)
        monkeypatch.setattr(routes_autonomous, "_fetch_github_checks", _fake_fetch)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Run to terminal",
                    "goal": "Complete autonomous stages via server loop",
                    "repository": "acme/repo",
                    "branch": "main",
                    "acceptance_criteria": ["terminal completed status"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            assert run_resp.status == 201
            run = await run_resp.json()

            until_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run['id']}/run-until-terminal",
                json={"max_steps": 8},
            )
            assert until_resp.status == 200
            payload = await until_resp.json()
            assert payload["terminal"] is True
            assert payload["terminal_status"] == "completed"
            assert payload["status"] == "completed"
            assert payload["steps_executed"] >= 1
            assert payload["run"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_pipeline_run_until_terminal_conflicts_with_other_active_run(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Run Until Terminal Conflict")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            task1_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Run 1",
                    "goal": "first run",
                    "acceptance_criteria": ["run exists"],
                },
            )
            assert task1_resp.status == 201
            task1 = await task1_resp.json()
            task2_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Run 2",
                    "goal": "second run",
                    "acceptance_criteria": ["run exists"],
                },
            )
            assert task2_resp.status == 201
            task2 = await task2_resp.json()

            run1_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task1["id"], "auto_start": False},
            )
            assert run1_resp.status == 201
            run1 = await run1_resp.json()
            run2_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task2["id"], "auto_start": False},
            )
            assert run2_resp.status == 201
            run2 = await run2_resp.json()

            until_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run1['id']}/run-until-terminal",
                json={"max_steps": 3},
            )
            assert until_resp.status == 409
            payload = await until_resp.json()
            assert payload["active_run_id"] == run2["id"]
            assert payload["requested_run_id"] == run1["id"]

    @pytest.mark.asyncio
    async def test_pipeline_execute_next_endpoint(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Execute Next")
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        from framework.server import routes_autonomous

        def _fake_resolve_execution_outcome(_manager, _run):
            return {"status": "completed", "reason": "test_completed"}

        def _fake_fetch(*, repository, ref, token, required_checks=None):
            assert repository == "acme/repo"
            assert ref == "main"
            assert token == "test-token"
            return {
                "repository": repository,
                "ref": ref,
                "checks": [
                    {"name": "lint", "passed": True, "severity": "error", "details": ""},
                    {"name": "tests", "passed": True, "severity": "error", "details": ""},
                ],
                "checks_summary": {"total": 2, "passed": 2, "failed": 0, "all_passed": True, "failures": []},
                "sha": "abc123",
            }

        monkeypatch.setattr(routes_autonomous, "_resolve_execution_outcome", _fake_resolve_execution_outcome)
        monkeypatch.setattr(routes_autonomous, "_fetch_github_checks", _fake_fetch)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Execute next task",
                    "goal": "Run from todo to terminal in one endpoint call",
                    "repository": "acme/repo",
                    "branch": "main",
                    "priority": "high",
                    "acceptance_criteria": ["task completed"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()

            exec_resp = await client.post(
                f"/api/projects/{pid}/autonomous/execute-next",
                json={"max_steps": 8, "auto_start": True},
            )
            assert exec_resp.status == 200
            payload = await exec_resp.json()
            assert payload["terminal"] is True
            assert payload["terminal_status"] == "completed"
            assert payload["status"] == "completed"
            assert payload["run"]["status"] == "completed"
            assert payload["selected_task"]["id"] == task["id"]

    @pytest.mark.asyncio
    async def test_pipeline_execute_next_empty_backlog(self):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Execute Next Empty")
        pid = created["id"]

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                f"/api/projects/{pid}/autonomous/execute-next",
                json={"max_steps": 3},
            )
            assert resp.status == 404
            payload = await resp.json()
            assert payload["error"] == "No todo tasks in backlog"

    @pytest.mark.asyncio
    async def test_pipeline_evaluate_github_endpoint(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous GitHub Eval")
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        from framework.server import routes_autonomous

        def _fake_fetch(*, repository, ref, token, required_checks=None):
            assert repository == "acme/repo"
            assert ref == "main"
            assert token == "test-token"
            return {
                "repository": repository,
                "ref": ref,
                "checks": [
                    {"name": "lint", "passed": True, "severity": "error", "details": ""},
                    {"name": "tests", "passed": True, "severity": "error", "details": ""},
                ],
                "checks_summary": {"total": 2, "passed": 2, "failed": 0, "all_passed": True, "failures": []},
                "sha": "abc123",
            }

        monkeypatch.setattr(routes_autonomous, "_fetch_github_checks", _fake_fetch)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "GitHub eval task",
                    "goal": "Evaluate from GitHub checks",
                    "acceptance_criteria": ["all checks green"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            # move to review stage first
            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )

            eval_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/evaluate/github",
                json={
                    "stage": "review",
                    "repository": "acme/repo",
                    "ref": "main",
                },
            )
            assert eval_resp.status == 200
            data = await eval_resp.json()
            assert data["current_stage"] == "validation"
            assert data["stage_states"]["review"] == "completed"

    @pytest.mark.asyncio
    async def test_pipeline_evaluate_github_includes_pr_review_feedback_in_report(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous GitHub Review Feedback")
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        from framework.server import routes_autonomous

        def _fake_fetch(*, repository, ref, token, required_checks=None):
            return {
                "repository": repository,
                "ref": ref,
                "checks": [{"name": "tests", "passed": True, "severity": "error", "details": ""}],
                "checks_summary": {"total": 1, "passed": 1, "failed": 0, "all_passed": True, "failures": []},
                "sha": "abc123",
            }

        def _fake_feedback(*, repository, pr_number, token):
            assert repository == "acme/repo"
            assert pr_number == 15
            return {
                "pr_number": pr_number,
                "reviews_summary": {
                    "total": 2,
                    "approved": 1,
                    "changes_requested": 1,
                    "commented": 0,
                    "dismissed": 0,
                    "pending": 0,
                },
                "review_comments_summary": {"total": 3},
                "issue_comments_summary": {"total": 1},
                "review_comments": [],
                "issue_comments": [],
            }

        monkeypatch.setattr(routes_autonomous, "_fetch_github_checks", _fake_fetch)
        monkeypatch.setattr(routes_autonomous, "_fetch_github_pr_feedback", _fake_feedback)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "GitHub eval with review feedback",
                    "goal": "Include PR feedback in report",
                    "acceptance_criteria": ["review feedback captured"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )

            eval_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/evaluate/github",
                json={
                    "stage": "review",
                    "repository": "acme/repo",
                    "ref": "main",
                    "pr_url": "https://github.com/acme/repo/pull/15",
                },
            )
            assert eval_resp.status == 200
            updated = await eval_resp.json()
            github_output = (
                updated.get("artifacts", {})
                .get("stages", {})
                .get("review", {})
                .get("output", {})
                .get("github", {})
            )
            assert github_output.get("review_feedback", {}).get("pr_number") == 15

            report_resp = await client.get(f"/api/projects/{pid}/autonomous/runs/{run_id}/report")
            assert report_resp.status == 200
            report_payload = await report_resp.json()
            report = report_payload.get("report", {})
            assert report.get("review_feedback", {}).get("reviews_summary", {}).get("changes_requested") == 1

    @pytest.mark.asyncio
    async def test_pipeline_evaluate_github_can_post_review_summary_comment(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous GitHub Review Comment")
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        from framework.server import routes_autonomous

        posted: list[dict[str, object]] = []

        def _fake_fetch(*, repository, ref, token, required_checks=None):
            return {
                "repository": repository,
                "ref": ref,
                "checks": [{"name": "tests", "passed": True, "severity": "error", "details": ""}],
                "checks_summary": {"total": 1, "passed": 1, "failed": 0, "all_passed": True, "failures": []},
                "sha": "abc123",
            }

        def _fake_feedback(*, repository, pr_number, token):
            return {
                "pr_number": pr_number,
                "reviews_summary": {
                    "total": 1,
                    "approved": 1,
                    "changes_requested": 0,
                    "commented": 0,
                    "dismissed": 0,
                    "pending": 0,
                },
                "review_comments_summary": {"total": 0},
                "issue_comments_summary": {"total": 0},
                "review_comments": [],
                "issue_comments": [],
            }

        def _fake_post(*, repository, pr_number, token, body):
            posted.append(
                {
                    "repository": repository,
                    "pr_number": pr_number,
                    "token": token,
                    "body": body,
                }
            )
            return {"id": 999, "html_url": "https://github.com/acme/repo/pull/15#issuecomment-999", "url": "api-url"}

        monkeypatch.setattr(routes_autonomous, "_fetch_github_checks", _fake_fetch)
        monkeypatch.setattr(routes_autonomous, "_fetch_github_pr_feedback", _fake_feedback)
        monkeypatch.setattr(routes_autonomous, "_github_post_issue_comment", _fake_post)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "GitHub eval post summary",
                    "goal": "Post summary comment",
                    "acceptance_criteria": ["comment posted"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )

            eval_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/evaluate/github",
                json={
                    "stage": "review",
                    "repository": "acme/repo",
                    "ref": "main",
                    "pr_url": "https://github.com/acme/repo/pull/15",
                    "post_review_summary": True,
                    "review_summary_comment": "Automated review summary from Hive",
                },
            )
            assert eval_resp.status == 200
            updated = await eval_resp.json()
            github_output = (
                updated.get("artifacts", {})
                .get("stages", {})
                .get("review", {})
                .get("output", {})
                .get("github", {})
            )
            assert github_output.get("posted_review_comment", {}).get("id") == 999
            assert len(posted) == 1
            assert posted[0]["pr_number"] == 15
            assert posted[0]["body"] == "Automated review summary from Hive"

    @pytest.mark.asyncio
    async def test_pipeline_evaluate_github_no_checks_success_policy(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(
            name="Autonomous GitHub No Checks Success",
            execution_template={"github": {"no_checks_policy": "success"}},
        )
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        from framework.server import routes_autonomous

        def _fake_fetch(*, repository, ref, token, required_checks=None):
            return {
                "repository": repository,
                "ref": ref,
                "checks": [],
                "checks_summary": {"total": 0, "passed": 0, "failed": 0, "all_passed": True, "failures": []},
                "sha": "abc123",
            }

        monkeypatch.setattr(routes_autonomous, "_fetch_github_checks", _fake_fetch)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "GitHub eval no checks success",
                    "goal": "Advance stage when no checks are returned",
                    "acceptance_criteria": ["advanced"],
                    "repository": "acme/repo",
                    "branch": "main",
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )

            eval_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/evaluate/github",
                json={"stage": "review"},
            )
            assert eval_resp.status == 200
            data = await eval_resp.json()
            assert data["current_stage"] == "validation"
            assert data["stage_states"]["review"] == "completed"

    @pytest.mark.asyncio
    async def test_pipeline_evaluate_github_uses_pr_url_when_ref_missing(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous GitHub PR URL")
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        from framework.server import routes_autonomous

        def _fake_resolve(*, token, repository, ref, pr_url):
            assert token == "test-token"
            assert repository == ""
            assert ref == ""
            assert pr_url == "https://github.com/acme/repo/pull/42"
            return "acme/repo", "deadbeef"

        def _fake_fetch(*, repository, ref, token, required_checks=None):
            assert repository == "acme/repo"
            assert ref == "deadbeef"
            return {
                "repository": repository,
                "ref": ref,
                "checks": [
                    {"name": "lint", "passed": True, "severity": "error", "details": ""},
                ],
                "checks_summary": {"total": 1, "passed": 1, "failed": 0, "all_passed": True, "failures": []},
                "sha": "deadbeef",
            }

        monkeypatch.setattr(routes_autonomous, "_resolve_github_target", _fake_resolve)
        monkeypatch.setattr(routes_autonomous, "_fetch_github_checks", _fake_fetch)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "GitHub eval from PR URL",
                    "goal": "Resolve target from PR URL",
                    "acceptance_criteria": ["resolved"],
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )

            eval_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/evaluate/github",
                json={
                    "stage": "review",
                    "pr_url": "https://github.com/acme/repo/pull/42",
                },
            )
            assert eval_resp.status == 200
            data = await eval_resp.json()
            assert data["current_stage"] == "validation"

    @pytest.mark.asyncio
    async def test_pipeline_loop_tick_uses_project_repository_and_default_ref(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(
            name="Autonomous Loop Tick Project Repo Fallback",
            repository="https://github.com/acme/repo.git",
            execution_template={"github": {"default_ref": "main"}},
        )
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        from framework.server import routes_autonomous

        def _fake_resolve(*, token, repository, ref, pr_url):
            assert token == "test-token"
            assert repository == "acme/repo"
            assert ref == "main"
            assert pr_url == ""
            return "acme/repo", "main"

        def _fake_fetch(*, repository, ref, token, required_checks=None):
            assert repository == "acme/repo"
            assert ref == "main"
            return {
                "repository": repository,
                "ref": ref,
                "checks": [{"name": "checks", "passed": True, "severity": "error", "details": ""}],
                "checks_summary": {"total": 1, "passed": 1, "failed": 0, "all_passed": True, "failures": []},
                "sha": "abc123",
            }

        monkeypatch.setattr(routes_autonomous, "_resolve_github_target", _fake_resolve)
        monkeypatch.setattr(routes_autonomous, "_fetch_github_checks", _fake_fetch)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Loop tick repo fallback",
                    "goal": "Use project-level repository/default_ref for github evaluate",
                    "acceptance_criteria": ["review auto-advanced"],
                },
            )
            assert task_resp.status == 201
            task = await task_resp.json()
            assert task["repository"] == "https://github.com/acme/repo.git"
            assert task["branch"] == "main"

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )

            tick = await client.post(
                f"/api/projects/{pid}/autonomous/loop/tick",
                json={},
            )
            assert tick.status == 200
            payload = await tick.json()
            assert payload["action"] == "advanced_with_github_checks"
            assert payload["run"]["current_stage"] == "validation"

    @pytest.mark.asyncio
    async def test_pipeline_auto_next_endpoint(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Auto Next")
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        from framework.server import routes_autonomous

        def _fake_resolve(*, token, repository, ref, pr_url):
            assert token == "test-token"
            return repository or "acme/repo", ref or "main"

        def _fake_fetch(*, repository, ref, token, required_checks=None):
            return {
                "repository": repository,
                "ref": ref,
                "checks": [{"name": "checks", "passed": True, "severity": "error", "details": ""}],
                "checks_summary": {"total": 1, "passed": 1, "failed": 0, "all_passed": True, "failures": []},
                "sha": "abc123",
            }

        monkeypatch.setattr(routes_autonomous, "_resolve_github_target", _fake_resolve)
        monkeypatch.setattr(routes_autonomous, "_fetch_github_checks", _fake_fetch)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Auto next task",
                    "goal": "Move stage via auto-next",
                    "acceptance_criteria": ["moved"],
                    "repository": "acme/repo",
                    "branch": "main",
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            # move to review first
            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )

            auto_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/auto-next",
                json={},
            )
            assert auto_resp.status == 200
            auto_data = await auto_resp.json()
            assert auto_data["current_stage"] == "validation"

    @pytest.mark.asyncio
    async def test_pipeline_auto_next_no_checks_manual_pending_policy(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(
            name="Autonomous Auto Next No Checks Manual",
            execution_template={"github": {"no_checks_policy": "manual_pending"}},
        )
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        monkeypatch.setenv("HIVE_AUTONOMOUS_AUTO_NEXT_FALLBACK", "error")

        from framework.server import routes_autonomous

        def _fake_fetch(*, repository, ref, token, required_checks=None):
            return {
                "repository": repository,
                "ref": ref,
                "checks": [],
                "checks_summary": {"total": 0, "passed": 0, "failed": 0, "all_passed": True, "failures": []},
                "sha": "abc123",
            }

        monkeypatch.setattr(routes_autonomous, "_fetch_github_checks", _fake_fetch)

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Auto next no checks manual",
                    "goal": "Defer when no checks and policy manual_pending",
                    "acceptance_criteria": ["deferred"],
                    "repository": "acme/repo",
                    "branch": "main",
                },
            )
            task = await task_resp.json()

            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )

            auto_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/auto-next",
                json={},
            )
            assert auto_resp.status == 202
            auto_data = await auto_resp.json()
            assert auto_data["deferred"] is True
            assert auto_data["action"] == "manual_evaluate_required"

    @pytest.mark.asyncio
    async def test_pipeline_auto_next_rejects_execution_stage(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Auto Next Reject")
        pid = created["id"]
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Auto next reject task",
                    "goal": "Reject on execution stage",
                    "acceptance_criteria": ["rejects"],
                },
            )
            task = await task_resp.json()
            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            auto_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/auto-next",
                json={},
            )
            assert auto_resp.status == 409

    @pytest.mark.asyncio
    async def test_pipeline_auto_next_deferred_without_token_in_manual_mode(self, monkeypatch):
        app = create_app()
        manager = app[APP_KEY_MANAGER]
        created = manager.create_project(name="Autonomous Auto Next Deferred")
        pid = created["id"]
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_PAT", raising=False)
        monkeypatch.setenv("HIVE_AUTONOMOUS_AUTO_NEXT_FALLBACK", "manual_pending")

        async with TestClient(TestServer(app)) as client:
            task_resp = await client.post(
                f"/api/projects/{pid}/autonomous/backlog",
                json={
                    "title": "Auto next deferred task",
                    "goal": "Defer without token",
                    "acceptance_criteria": ["deferred"],
                    "repository": "acme/repo",
                    "branch": "main",
                },
            )
            task = await task_resp.json()
            run_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs",
                json={"task_id": task["id"], "auto_start": True},
            )
            run = await run_resp.json()
            run_id = run["id"]

            await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/advance",
                json={"stage": "execution", "result": "success"},
            )
            deferred_resp = await client.post(
                f"/api/projects/{pid}/autonomous/runs/{run_id}/auto-next",
                json={},
            )
            assert deferred_resp.status == 202
            deferred = await deferred_resp.json()
            assert deferred["deferred"] is True
            assert deferred["action"] == "manual_evaluate_required"


class TestCleanupStaleActiveSessions:
    """Tests for _cleanup_stale_active_sessions with two-layer protection."""

    def _make_manager(self):
        from framework.server.session_manager import SessionManager

        return SessionManager()

    def _write_state(self, session_dir: Path, status: str, pid: int | None = None) -> None:
        session_dir.mkdir(parents=True, exist_ok=True)
        state: dict = {"status": status, "session_id": session_dir.name}
        if pid is not None:
            state["pid"] = pid
        (session_dir / "state.json").write_text(json.dumps(state))

    def _read_state(self, session_dir: Path) -> dict:
        return json.loads((session_dir / "state.json").read_text())

    def test_stale_session_is_cancelled(self, tmp_path, monkeypatch):
        """Truly stale active sessions (no live tracking, no PID) get cancelled."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        agent_path = Path("my_agent")
        sessions_dir = tmp_path / ".hive" / "agents" / "my_agent" / "sessions"
        session_dir = sessions_dir / "session_stale_001"

        self._write_state(session_dir, "active")

        mgr = self._make_manager()
        mgr._cleanup_stale_active_sessions(agent_path)

        state = self._read_state(session_dir)
        assert state["status"] == "cancelled"
        assert "Stale session" in state["result"]["error"]

    def test_live_in_memory_session_is_skipped(self, tmp_path, monkeypatch):
        """Sessions tracked in self._sessions must NOT be cancelled (Layer 1)."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        agent_path = Path("my_agent")
        sessions_dir = tmp_path / ".hive" / "agents" / "my_agent" / "sessions"
        session_dir = sessions_dir / "session_live_002"

        self._write_state(session_dir, "active")

        mgr = self._make_manager()
        # Simulate a live session in the manager's in-memory map
        mgr._sessions["session_live_002"] = MagicMock()

        mgr._cleanup_stale_active_sessions(agent_path)

        state = self._read_state(session_dir)
        assert state["status"] == "active", "Live in-memory session should NOT be cancelled"

    def test_session_with_live_pid_is_skipped(self, tmp_path, monkeypatch):
        """Sessions whose owning PID is still alive must NOT be cancelled (Layer 2)."""
        import os

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        agent_path = Path("my_agent")
        sessions_dir = tmp_path / ".hive" / "agents" / "my_agent" / "sessions"
        session_dir = sessions_dir / "session_pid_003"

        # Use the current process PID — guaranteed to be alive
        self._write_state(session_dir, "active", pid=os.getpid())

        mgr = self._make_manager()
        mgr._cleanup_stale_active_sessions(agent_path)

        state = self._read_state(session_dir)
        assert state["status"] == "active", "Session with live PID should NOT be cancelled"

    def test_session_with_dead_pid_is_cancelled(self, tmp_path, monkeypatch):
        """Sessions whose owning PID is dead should be cancelled."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        agent_path = Path("my_agent")
        sessions_dir = tmp_path / ".hive" / "agents" / "my_agent" / "sessions"
        session_dir = sessions_dir / "session_dead_004"

        # Use a PID that is almost certainly not running
        self._write_state(session_dir, "active", pid=999999999)

        mgr = self._make_manager()
        mgr._cleanup_stale_active_sessions(agent_path)

        state = self._read_state(session_dir)
        assert state["status"] == "cancelled"
        assert "Stale session" in state["result"]["error"]

    def test_paused_session_is_never_touched(self, tmp_path, monkeypatch):
        """Paused sessions should remain intact regardless of PID or tracking."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        agent_path = Path("my_agent")
        sessions_dir = tmp_path / ".hive" / "agents" / "my_agent" / "sessions"
        session_dir = sessions_dir / "session_paused_005"

        self._write_state(session_dir, "paused")

        mgr = self._make_manager()
        mgr._cleanup_stale_active_sessions(agent_path)

        state = self._read_state(session_dir)
        assert state["status"] == "paused", "Paused sessions must remain untouched"

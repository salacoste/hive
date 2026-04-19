"""Execution control routes — trigger, inject, chat, resume, stop, replay."""

import asyncio
import heapq
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web

from framework.credentials.validation import validate_agent_credentials
from framework.graph.conversation import LEGACY_RUN_ID
from framework.server.app import APP_KEY_MANAGER, resolve_session, safe_path_segment, sessions_dir
from framework.server.project_policy import resolve_effective_policy
from framework.server.routes_sessions import _credential_error_response

logger = logging.getLogger(__name__)

APP_KEY_PROJECT_EXEC_QUEUE_LOCK: web.AppKey[asyncio.Lock] = web.AppKey(
    "project_execution_queue_lock", asyncio.Lock
)
APP_KEY_PROJECT_EXEC_QUEUES: web.AppKey[dict[str, list["_QueuedExecution"]]] = web.AppKey(
    "project_execution_queues", dict
)
APP_KEY_PROJECT_EXEC_TASKS: web.AppKey[dict[str, "_QueuedExecution"]] = web.AppKey(
    "project_execution_tasks", dict
)
APP_KEY_PROJECT_EXEC_STATE: web.AppKey[dict[str, int]] = web.AppKey("project_execution_state", dict)
APP_KEY_PROJECT_EXEC_QUEUE_STOP: web.AppKey[asyncio.Event] = web.AppKey(
    "project_execution_queue_stop", asyncio.Event
)
APP_KEY_PROJECT_EXEC_QUEUE_TASK: web.AppKey[asyncio.Task] = web.AppKey(
    "project_execution_queue_task", asyncio.Task
)


@dataclass(order=True)
class _QueuedExecution:
    priority: int
    seq: int
    task_id: str = field(compare=False)
    project_id: str = field(compare=False)
    session_id: str = field(compare=False)
    mode: str = field(compare=False)  # trigger|resume|replay
    payload: dict[str, Any] = field(compare=False)
    enqueued_at: float = field(compare=False, default_factory=time.time)
    status: str = field(compare=False, default="queued")  # queued|dispatched|failed
    execution_id: str | None = field(compare=False, default=None)
    error: str | None = field(compare=False, default=None)
    dispatched_at: float | None = field(compare=False, default=None)


def _project_queue_limit(app: web.Application, project_id: str) -> int:
    manager: Any = app[APP_KEY_MANAGER]
    project = manager.get_project(project_id) if hasattr(manager, "get_project") else None
    if isinstance(project, dict):
        raw = project.get("max_concurrent_runs")
        if raw is not None:
            try:
                value = int(raw)
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass
    fallback = os.environ.get("HIVE_PROJECT_MAX_CONCURRENT_RUNS", "1").strip()
    try:
        value = int(fallback)
        return value if value > 0 else 1
    except ValueError:
        return 1


def _active_project_runs(app: web.Application, project_id: str) -> int:
    manager: Any = app[APP_KEY_MANAGER]
    active = 0
    for session in manager.list_sessions(project_id=project_id):
        runtime = getattr(session, "graph_runtime", None)
        if runtime is None:
            continue
        for graph_id in runtime.list_graphs():
            reg = runtime.get_graph_registration(graph_id)
            if reg is None:
                continue
            for stream in reg.streams.values():
                active += len(getattr(stream, "active_execution_ids", set()) or set())
    return active


async def _dispatch_project_queue(app: web.Application, project_id: str) -> None:
    manager: Any = app[APP_KEY_MANAGER]
    lock: asyncio.Lock = app[APP_KEY_PROJECT_EXEC_QUEUE_LOCK]
    async with lock:
        queue_map: dict[str, list[_QueuedExecution]] = app[APP_KEY_PROJECT_EXEC_QUEUES]
        tasks: dict[str, _QueuedExecution] = app[APP_KEY_PROJECT_EXEC_TASKS]
        queue = queue_map.get(project_id, [])
        if not queue:
            return
        limit = _project_queue_limit(app, project_id)
        active = _active_project_runs(app, project_id)
        while queue and active < limit:
            item = heapq.heappop(queue)
            session = manager.get_session(item.session_id)
            if session is None:
                item.status = "failed"
                item.error = "Session not found"
                tasks[item.task_id] = item
                continue
            if getattr(session, "project_id", None) != item.project_id:
                item.status = "failed"
                item.error = "Session project mismatch"
                tasks[item.task_id] = item
                continue
            runtime = getattr(session, "graph_runtime", None)
            if runtime is None:
                item.status = "failed"
                item.error = "No graph loaded in this session"
                tasks[item.task_id] = item
                continue
            try:
                if item.mode == "trigger":
                    p = item.payload
                    execution_id = await runtime.trigger(
                        p["entry_point_id"],
                        p["input_data"],
                        session_state=p["session_state"],
                    )
                    if session.queen_executor:
                        node = session.queen_executor.node_registry.get("queen")
                        if node and hasattr(node, "cancel_current_turn"):
                            node.cancel_current_turn()
                    if session.phase_state is not None:
                        await session.phase_state.switch_to_running(source="frontend")
                elif item.mode == "resume":
                    p = item.payload
                    execution_id = await runtime.trigger(
                        p["entry_point_id"],
                        input_data=p["input_data"],
                        session_state=p["session_state"],
                    )
                elif item.mode == "replay":
                    p = item.payload
                    execution_id = await runtime.trigger(
                        p["entry_point_id"],
                        input_data={},
                        session_state=p["session_state"],
                    )
                else:
                    raise ValueError(f"Unknown queue mode: {item.mode}")
                item.status = "dispatched"
                item.execution_id = execution_id
                item.dispatched_at = time.time()
                tasks[item.task_id] = item
            except Exception as e:
                item.status = "failed"
                item.error = str(e)
                tasks[item.task_id] = item
            active = _active_project_runs(app, project_id)


async def _queue_dispatcher_loop(app: web.Application) -> None:
    while not app[APP_KEY_PROJECT_EXEC_QUEUE_STOP].is_set():
        try:
            queue_map: dict[str, list[_QueuedExecution]] = app[APP_KEY_PROJECT_EXEC_QUEUES]
            for project_id, queue in list(queue_map.items()):
                if not queue:
                    continue
                await _dispatch_project_queue(app, project_id)
        except Exception:
            logger.exception("Project execution queue dispatcher iteration failed")
        await asyncio.sleep(0.5)


async def _queue_dispatcher_startup(app: web.Application) -> None:
    app[APP_KEY_PROJECT_EXEC_QUEUE_LOCK] = asyncio.Lock()
    app[APP_KEY_PROJECT_EXEC_QUEUES] = {}
    app[APP_KEY_PROJECT_EXEC_TASKS] = {}
    app[APP_KEY_PROJECT_EXEC_STATE] = {"seq": 0}
    app[APP_KEY_PROJECT_EXEC_QUEUE_STOP] = asyncio.Event()
    app[APP_KEY_PROJECT_EXEC_QUEUE_TASK] = asyncio.create_task(
        _queue_dispatcher_loop(app), name="project-execution-queue-dispatcher"
    )


async def _queue_dispatcher_cleanup(app: web.Application) -> None:
    stop_event: asyncio.Event | None = app.get(APP_KEY_PROJECT_EXEC_QUEUE_STOP)
    task: asyncio.Task | None = app.get(APP_KEY_PROJECT_EXEC_QUEUE_TASK)
    if stop_event is not None:
        stop_event.set()
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _start_or_queue_execution(
    app: web.Application,
    *,
    session: Any,
    mode: str,
    payload: dict[str, Any],
    queue_if_busy: bool,
    priority: int,
) -> web.Response:
    project_id = getattr(session, "project_id", "default")
    manager: Any = app[APP_KEY_MANAGER]
    project = manager.get_project(project_id) if hasattr(manager, "get_project") else None
    effective_policy = resolve_effective_policy(project)
    risk_controls = effective_policy.get("effective", {}).get("risk_controls", {})
    if isinstance(risk_controls, dict) and risk_controls.get("allowed") is False:
        return web.json_response(
            {
                "error": "Execution blocked by project policy",
                "project_id": project_id,
                "effective_policy": effective_policy.get("effective", {}),
            },
            status=403,
        )

    limit = _project_queue_limit(app, project_id)
    active = _active_project_runs(app, project_id)
    if active < limit:
        runtime = session.graph_runtime
        if mode == "trigger":
            execution_id = await runtime.trigger(
                payload["entry_point_id"],
                payload["input_data"],
                session_state=payload["session_state"],
            )
            if session.queen_executor:
                node = session.queen_executor.node_registry.get("queen")
                if node and hasattr(node, "cancel_current_turn"):
                    node.cancel_current_turn()
            if session.phase_state is not None:
                await session.phase_state.switch_to_running(source="frontend")
            return web.json_response({"execution_id": execution_id})
        if mode == "resume":
            execution_id = await runtime.trigger(
                payload["entry_point_id"],
                input_data=payload["input_data"],
                session_state=payload["session_state"],
            )
            return web.json_response(
                {
                    "execution_id": execution_id,
                    "resumed_from": payload["worker_session_id"],
                    "checkpoint_id": payload["checkpoint_id"],
                }
            )
        if mode == "replay":
            execution_id = await runtime.trigger(
                payload["entry_point_id"],
                input_data={},
                session_state=payload["session_state"],
            )
            return web.json_response(
                {
                    "execution_id": execution_id,
                    "replayed_from": payload["worker_session_id"],
                    "checkpoint_id": payload["checkpoint_id"],
                }
            )

    if not queue_if_busy:
        return web.json_response(
            {
                "error": "Project execution limit reached",
                "project_id": project_id,
                "active_runs": active,
                "max_concurrent_runs": limit,
            },
            status=409,
        )

    lock: asyncio.Lock = app[APP_KEY_PROJECT_EXEC_QUEUE_LOCK]
    async with lock:
        state: dict[str, int] = app[APP_KEY_PROJECT_EXEC_STATE]
        seq = int(state.get("seq", 0)) + 1
        state["seq"] = seq
        task_id = f"qexec_{uuid.uuid4().hex[:12]}"
        item = _QueuedExecution(
            priority=priority,
            seq=seq,
            task_id=task_id,
            project_id=project_id,
            session_id=session.id,
            mode=mode,
            payload=payload,
        )
        queue_map: dict[str, list[_QueuedExecution]] = app[APP_KEY_PROJECT_EXEC_QUEUES]
        queue_map.setdefault(project_id, [])
        heapq.heappush(queue_map[project_id], item)
        app[APP_KEY_PROJECT_EXEC_TASKS][task_id] = item

    return web.json_response(
        {
            "queued": True,
            "task_id": task_id,
            "project_id": project_id,
            "active_runs": active,
            "max_concurrent_runs": limit,
            "priority": priority,
        },
        status=202,
    )


def _load_checkpoint_run_id(cp_path) -> str | None:
    try:
        checkpoint = json.loads(cp_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    run_id = checkpoint.get("run_id")
    if isinstance(run_id, str) and run_id:
        return run_id
    return LEGACY_RUN_ID


async def handle_trigger(request: web.Request) -> web.Response:
    """POST /api/sessions/{session_id}/trigger — start an execution.

    Body: {"entry_point_id": "default", "input_data": {...}, "session_state": {...}?}
    """
    session, err = resolve_session(request)
    if err:
        return err

    if not session.graph_runtime:
        return web.json_response({"error": "No graph loaded in this session"}, status=503)

    # Validate credentials before running — deferred from load time to avoid
    # showing the modal before the user clicks Run.  Runs in executor because
    # validate_agent_credentials makes blocking HTTP health-check calls.
    if session.runner:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None, lambda: validate_agent_credentials(session.runner.graph.nodes)
            )
        except Exception as e:
            agent_path = str(session.worker_path) if session.worker_path else ""
            resp = _credential_error_response(e, agent_path)
            if resp is not None:
                return resp

        # Resync MCP servers if credentials were added since the worker loaded
        # (e.g. user connected an OAuth account mid-session via Aden UI).
        try:
            await loop.run_in_executor(
                None, lambda: session.runner._tool_registry.resync_mcp_servers_if_needed()
            )
        except Exception as e:
            logger.warning("MCP resync failed: %s", e)

    body = await request.json()
    entry_point_id = body.get("entry_point_id", "default")
    input_data = body.get("input_data", {})
    session_state = body.get("session_state") or {}
    queue_if_busy = bool(body.get("queue_if_busy", False))
    priority = int(body.get("priority", 100))

    # Scope the worker execution to the live session ID
    if "resume_session_id" not in session_state:
        session_state["resume_session_id"] = session.id

    return await _start_or_queue_execution(
        request.app,
        session=session,
        mode="trigger",
        payload={
            "entry_point_id": entry_point_id,
            "input_data": input_data,
            "session_state": session_state,
        },
        queue_if_busy=queue_if_busy,
        priority=priority,
    )


async def handle_inject(request: web.Request) -> web.Response:
    """POST /api/sessions/{session_id}/inject — inject input into a waiting node.

    Body: {"node_id": "...", "content": "...", "graph_id": "..."}
    """
    session, err = resolve_session(request)
    if err:
        return err

    if not session.graph_runtime:
        return web.json_response({"error": "No graph loaded in this session"}, status=503)

    body = await request.json()
    node_id = body.get("node_id")
    content = body.get("content", "")
    graph_id = body.get("graph_id")

    if not node_id:
        return web.json_response({"error": "node_id is required"}, status=400)

    delivered = await session.graph_runtime.inject_input(node_id, content, graph_id=graph_id)
    return web.json_response({"delivered": delivered})


async def handle_chat(request: web.Request) -> web.Response:
    """POST /api/sessions/{session_id}/chat — send a message to the queen.

    The input box is permanently connected to the queen agent, including
    replies to worker-originated questions. The queen decides whether to
    relay the user's answer back into the worker via inject_message().

    Body: {"message": "hello", "images": [{"type": "image_url", "image_url": {"url": "data:..."}}]}

    The optional ``images`` field accepts a list of OpenAI-format image_url
    content blocks.  The frontend encodes images as base64 data URIs.
    """
    session, err = resolve_session(request)
    if err:
        logger.debug("[handle_chat] Session resolution failed: %s", err)
        return err

    body = await request.json()
    message = body.get("message", "")
    display_message = body.get("display_message")
    client_message_id = body.get("client_message_id")
    image_content = body.get("images") or None  # list[dict] | None

    logger.debug(
        "[handle_chat] session_id=%s, message_len=%d, has_images=%s",
        session.id,
        len(message),
        bool(image_content),
    )
    logger.debug("[handle_chat] session.queen_executor=%s", session.queen_executor)

    if not message and not image_content:
        return web.json_response({"error": "message is required"}, status=400)

    queen_executor = session.queen_executor
    if queen_executor is not None:
        logger.debug("[handle_chat] Queen executor exists, looking for 'queen' node...")
        logger.debug(
            "[handle_chat] node_registry type=%s, id=%s",
            type(queen_executor.node_registry),
            id(queen_executor.node_registry),
        )
        logger.debug(
            "[handle_chat] node_registry keys: %s", list(queen_executor.node_registry.keys())
        )
        node = queen_executor.node_registry.get("queen")
        logger.debug(
            "[handle_chat] node=%s, node_type=%s", node, type(node).__name__ if node else None
        )
        logger.debug(
            "[handle_chat] has_inject_event=%s", hasattr(node, "inject_event") if node else False
        )

        # Race condition: executor exists but node not created yet (still initializing)
        if node is None and session.queen_task is not None and not session.queen_task.done():
            logger.warning(
                "[handle_chat] Queen executor exists but node"
                " not ready yet (initializing). Waiting..."
            )
            # Wait a short time for initialization to progress
            import asyncio

            for _ in range(50):  # Max 5 seconds
                await asyncio.sleep(0.1)
                node = queen_executor.node_registry.get("queen")
                if node is not None:
                    logger.debug("[handle_chat] Node appeared after waiting")
                    break
            else:
                logger.error("[handle_chat] Node still not available after 5s wait")

        if node is not None and hasattr(node, "inject_event"):
            # Publish BEFORE inject_event so event-bus listeners (for example
            # recall cache refreshers) run before queen turn processing starts.
            from framework.runtime.event_bus import AgentEvent, EventType

            await session.event_bus.publish(
                AgentEvent(
                    type=EventType.CLIENT_INPUT_RECEIVED,
                    stream_id="queen",
                    node_id="queen",
                    execution_id=session.id,
                    data={
                        # Allow the UI to display a user-friendly echo while
                        # the queen receives a richer relay wrapper.
                        "content": display_message if display_message is not None else message,
                        "image_count": len(image_content) if image_content else 0,
                        "client_message_id": client_message_id,
                        "source": "web",
                    },
                )
            )
            try:
                logger.debug("[handle_chat] Calling node.inject_event()...")
                await node.inject_event(message, is_client_input=True, image_content=image_content)
                logger.debug("[handle_chat] inject_event() completed successfully")
            except Exception as e:
                logger.exception("[handle_chat] inject_event() failed: %s", e)
                raise
            return web.json_response(
                {
                    "status": "queen",
                    "delivered": True,
                }
            )
        else:
            if node is None:
                logger.error(
                    "[handle_chat] CRITICAL: Queen node is None!"
                    " node_registry has %d keys: %s,"
                    " queen_task=%s, queen_task_done=%s",
                    len(queen_executor.node_registry),
                    list(queen_executor.node_registry.keys()),
                    session.queen_task,
                    session.queen_task.done() if session.queen_task else None,
                )
            else:
                logger.error(
                    "[handle_chat] CRITICAL: Queen node exists"
                    " but missing inject_event!"
                    " node_attrs=%s",
                    [a for a in dir(node) if not a.startswith("_")],
                )

    # Queen is dead — try to revive her
    logger.warning(
        "[handle_chat] Queen is dead for session '%s', reviving on /chat request", session.id
    )
    manager: Any = request.app[APP_KEY_MANAGER]
    try:
        logger.debug("[handle_chat] Calling manager.revive_queen()...")
        await manager.revive_queen(session)
        logger.debug("[handle_chat] revive_queen() completed successfully")
        # Inject the user's message into the revived queen's queue so the
        # event loop drains it and clears any restored pending_input_state.
        _revived_executor = session.queen_executor
        _revived_node = _revived_executor.node_registry.get("queen") if _revived_executor else None
        if _revived_node is not None and hasattr(_revived_node, "inject_event"):
            from framework.runtime.event_bus import AgentEvent, EventType

            await session.event_bus.publish(
                AgentEvent(
                    type=EventType.CLIENT_INPUT_RECEIVED,
                    stream_id="queen",
                    node_id="queen",
                    execution_id=session.id,
                    data={
                        "content": display_message if display_message is not None else message,
                        "image_count": len(image_content) if image_content else 0,
                        "client_message_id": client_message_id,
                        "source": "web",
                    },
                )
            )
            await _revived_node.inject_event(
                message, is_client_input=True, image_content=image_content
            )
        return web.json_response(
            {
                "status": "queen_revived",
                "delivered": True,
            }
        )
    except Exception as e:
        logger.exception("[handle_chat] Failed to revive queen: %s", e)
        return web.json_response({"error": "Queen not available"}, status=503)


async def handle_queen_context(request: web.Request) -> web.Response:
    """POST /api/sessions/{session_id}/queen-context — queue context for the queen.

    Unlike /chat, this does NOT trigger an LLM response. The message is
    queued in the queen's injection queue and will be drained on her next
    natural iteration (prefixed with [External event]:).

    Body: {"message": "..."}
    """
    session, err = resolve_session(request)
    if err:
        return err

    body = await request.json()
    message = body.get("message", "")

    if not message:
        return web.json_response({"error": "message is required"}, status=400)

    queen_executor = session.queen_executor
    if queen_executor is not None:
        node = queen_executor.node_registry.get("queen")
        if node is not None and hasattr(node, "inject_event"):
            await node.inject_event(message, is_client_input=False)
            return web.json_response({"status": "queued", "delivered": True})

    # Queen is dead — try to revive her
    logger.warning(
        "Queen is dead for session '%s', reviving on /queen-context request",
        session.id,
    )
    manager: Any = request.app[APP_KEY_MANAGER]
    try:
        await manager.revive_queen(session)
        # After revival, deliver the message
        queen_executor = session.queen_executor
        if queen_executor is not None:
            node = queen_executor.node_registry.get("queen")
            if node is not None and hasattr(node, "inject_event"):
                await node.inject_event(message, is_client_input=False)
                return web.json_response({"status": "queued_revived", "delivered": True})
    except Exception as e:
        logger.error("Failed to revive queen for context: %s", e)

    return web.json_response({"error": "Queen not available"}, status=503)


async def handle_goal_progress(request: web.Request) -> web.Response:
    """GET /api/sessions/{session_id}/goal-progress — evaluate goal progress."""
    session, err = resolve_session(request)
    if err:
        return err

    if not session.graph_runtime:
        return web.json_response({"error": "No graph loaded in this session"}, status=503)

    progress = await session.graph_runtime.get_goal_progress()
    return web.json_response(progress, dumps=lambda obj: json.dumps(obj, default=str))


async def handle_resume(request: web.Request) -> web.Response:
    """POST /api/sessions/{session_id}/resume — resume a paused execution.

    Body: {"session_id": "...", "checkpoint_id": "..." (optional)}
    """
    session, err = resolve_session(request)
    if err:
        return err

    if not session.graph_runtime:
        return web.json_response({"error": "No graph loaded in this session"}, status=503)

    body = await request.json()
    worker_session_id = body.get("session_id")
    checkpoint_id = body.get("checkpoint_id")
    queue_if_busy = bool(body.get("queue_if_busy", False))
    priority = int(body.get("priority", 100))

    if not worker_session_id:
        return web.json_response({"error": "session_id is required"}, status=400)

    worker_session_id = safe_path_segment(worker_session_id)
    if checkpoint_id:
        checkpoint_id = safe_path_segment(checkpoint_id)

    # Read session state
    session_dir = sessions_dir(session) / worker_session_id
    state_path = session_dir / "state.json"
    if not state_path.exists():
        return web.json_response({"error": "Session not found"}, status=404)

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return web.json_response({"error": f"Failed to read session: {e}"}, status=500)

    if not checkpoint_id:
        return web.json_response(
            {"error": "checkpoint_id is required; non-checkpoint resume is no longer supported"},
            status=400,
        )

    cp_path = session_dir / "checkpoints" / f"{checkpoint_id}.json"
    if not cp_path.exists():
        return web.json_response({"error": "Checkpoint not found"}, status=404)

    resume_session_state = {
        "resume_session_id": worker_session_id,
        "resume_from_checkpoint": checkpoint_id,
        "run_id": _load_checkpoint_run_id(cp_path),
    }

    entry_points = session.graph_runtime.get_entry_points()
    if not entry_points:
        return web.json_response({"error": "No entry points available"}, status=400)

    input_data = state.get("input_data", {})

    return await _start_or_queue_execution(
        request.app,
        session=session,
        mode="resume",
        payload={
            "entry_point_id": entry_points[0].id,
            "input_data": input_data,
            "session_state": resume_session_state,
            "worker_session_id": worker_session_id,
            "checkpoint_id": checkpoint_id,
        },
        queue_if_busy=queue_if_busy,
        priority=priority,
    )


async def handle_pause(request: web.Request) -> web.Response:
    """POST /api/sessions/{session_id}/pause — pause the worker (queen stays alive).

    Mirrors the queen's stop_graph() tool: cancels all active worker
    executions, pauses timers so nothing auto-restarts, but does NOT
    touch the queen so she can observe and react to the pause.
    """
    session, err = resolve_session(request)
    if err:
        return err

    if not session.graph_runtime:
        return web.json_response({"error": "No graph loaded in this session"}, status=503)

    runtime = session.graph_runtime
    cancelled = []

    for graph_id in runtime.list_graphs():
        reg = runtime.get_graph_registration(graph_id)
        if reg is None:
            continue
        for _ep_id, stream in reg.streams.items():
            # Signal shutdown on active nodes to abort in-flight LLM streams
            for executor in stream._active_executors.values():
                for node in executor.node_registry.values():
                    if hasattr(node, "signal_shutdown"):
                        node.signal_shutdown()
                    if hasattr(node, "cancel_current_turn"):
                        node.cancel_current_turn()

            for exec_id in list(stream.active_execution_ids):
                try:
                    ok = await stream.cancel_execution(exec_id, reason="Execution paused by user")
                    if ok:
                        cancelled.append(exec_id)
                except Exception:
                    pass

    # Pause timers so the next tick doesn't restart execution
    runtime.pause_timers()

    # Switch to staging (agent still loaded, ready to re-run)
    if session.phase_state is not None:
        await session.phase_state.switch_to_staging(source="frontend")

    await _dispatch_project_queue(request.app, getattr(session, "project_id", "default"))

    return web.json_response(
        {
            "stopped": bool(cancelled),
            "cancelled": cancelled,
            "timers_paused": True,
        }
    )


async def handle_stop(request: web.Request) -> web.Response:
    """POST /api/sessions/{session_id}/stop — cancel a running execution.

    Body: {"execution_id": "..."}
    """
    session, err = resolve_session(request)
    if err:
        return err

    if not session.graph_runtime:
        return web.json_response({"error": "No graph loaded in this session"}, status=503)

    body = await request.json()
    execution_id = body.get("execution_id")

    if not execution_id:
        return web.json_response({"error": "execution_id is required"}, status=400)

    for graph_id in session.graph_runtime.list_graphs():
        reg = session.graph_runtime.get_graph_registration(graph_id)
        if reg is None:
            continue
        for _ep_id, stream in reg.streams.items():
            # Signal shutdown on active nodes to abort in-flight LLM streams
            for executor in stream._active_executors.values():
                for node in executor.node_registry.values():
                    if hasattr(node, "signal_shutdown"):
                        node.signal_shutdown()
                    if hasattr(node, "cancel_current_turn"):
                        node.cancel_current_turn()

            cancelled = await stream.cancel_execution(
                execution_id, reason="Execution stopped by user"
            )
            if cancelled:
                # Cancel queen's in-progress LLM turn
                if session.queen_executor:
                    node = session.queen_executor.node_registry.get("queen")
                    if node and hasattr(node, "cancel_current_turn"):
                        node.cancel_current_turn()

                # Switch to staging (agent still loaded, ready to re-run)
                if session.phase_state is not None:
                    await session.phase_state.switch_to_staging(source="frontend")

                await _dispatch_project_queue(
                    request.app,
                    getattr(session, "project_id", "default"),
                )

                return web.json_response(
                    {
                        "stopped": True,
                        "execution_id": execution_id,
                    }
                )

    return web.json_response({"stopped": False, "error": "Execution not found"}, status=404)


async def handle_replay(request: web.Request) -> web.Response:
    """POST /api/sessions/{session_id}/replay — re-run from a checkpoint.

    Body: {"session_id": "...", "checkpoint_id": "..."}
    """
    session, err = resolve_session(request)
    if err:
        return err

    if not session.graph_runtime:
        return web.json_response({"error": "No graph loaded in this session"}, status=503)

    body = await request.json()
    worker_session_id = body.get("session_id")
    checkpoint_id = body.get("checkpoint_id")
    queue_if_busy = bool(body.get("queue_if_busy", False))
    priority = int(body.get("priority", 100))

    if not worker_session_id:
        return web.json_response({"error": "session_id is required"}, status=400)
    if not checkpoint_id:
        return web.json_response({"error": "checkpoint_id is required"}, status=400)

    worker_session_id = safe_path_segment(worker_session_id)
    checkpoint_id = safe_path_segment(checkpoint_id)

    cp_path = sessions_dir(session) / worker_session_id / "checkpoints" / f"{checkpoint_id}.json"
    if not cp_path.exists():
        return web.json_response({"error": "Checkpoint not found"}, status=404)

    entry_points = session.graph_runtime.get_entry_points()
    if not entry_points:
        return web.json_response({"error": "No entry points available"}, status=400)

    replay_session_state = {
        "resume_session_id": worker_session_id,
        "resume_from_checkpoint": checkpoint_id,
        "run_id": _load_checkpoint_run_id(cp_path),
    }

    return await _start_or_queue_execution(
        request.app,
        session=session,
        mode="replay",
        payload={
            "entry_point_id": entry_points[0].id,
            "session_state": replay_session_state,
            "worker_session_id": worker_session_id,
            "checkpoint_id": checkpoint_id,
        },
        queue_if_busy=queue_if_busy,
        priority=priority,
    )

async def handle_project_queue(request: web.Request) -> web.Response:
    project_id = request.match_info["project_id"]
    manager: Any = request.app[APP_KEY_MANAGER]
    if manager.get_project(project_id) is None:
        return web.json_response({"error": f"Project '{project_id}' not found"}, status=404)

    queue_map: dict[str, list[_QueuedExecution]] = request.app[APP_KEY_PROJECT_EXEC_QUEUES]
    tasks: dict[str, _QueuedExecution] = request.app[APP_KEY_PROJECT_EXEC_TASKS]
    items = list(queue_map.get(project_id, []))
    items.sort(key=lambda i: (i.priority, i.seq))
    queued = [
        {
            "task_id": i.task_id,
            "session_id": i.session_id,
            "mode": i.mode,
            "priority": i.priority,
            "status": i.status,
            "enqueued_at": i.enqueued_at,
        }
        for i in items
    ]
    recent = [
        {
            "task_id": i.task_id,
            "session_id": i.session_id,
            "mode": i.mode,
            "priority": i.priority,
            "status": i.status,
            "execution_id": i.execution_id,
            "error": i.error,
            "enqueued_at": i.enqueued_at,
            "dispatched_at": i.dispatched_at,
        }
        for i in tasks.values()
        if i.project_id == project_id and i.status != "queued"
    ]
    recent.sort(key=lambda i: (i.get("dispatched_at") or 0, i["enqueued_at"]), reverse=True)
    return web.json_response(
        {
            "project_id": project_id,
            "max_concurrent_runs": _project_queue_limit(request.app, project_id),
            "active_runs": _active_project_runs(request.app, project_id),
            "queued": queued,
            "recent": recent[:50],
        }
    )


async def handle_cancel_queen(request: web.Request) -> web.Response:
    """POST /api/sessions/{session_id}/cancel-queen — cancel the queen's current LLM turn."""
    session, err = resolve_session(request)
    if err:
        return err
    queen_executor = session.queen_executor
    if queen_executor is None:
        return web.json_response({"cancelled": False, "error": "Queen not active"}, status=404)
    node = queen_executor.node_registry.get("queen")
    if node is None or not hasattr(node, "cancel_current_turn"):
        return web.json_response({"cancelled": False, "error": "Queen node not found"}, status=404)
    node.cancel_current_turn()
    return web.json_response({"cancelled": True})


def register_routes(app: web.Application) -> None:
    """Register execution control routes."""
    app.on_startup.append(_queue_dispatcher_startup)
    app.on_cleanup.append(_queue_dispatcher_cleanup)
    # Session-primary routes
    app.router.add_post("/api/sessions/{session_id}/trigger", handle_trigger)
    app.router.add_post("/api/sessions/{session_id}/inject", handle_inject)
    app.router.add_post("/api/sessions/{session_id}/chat", handle_chat)
    app.router.add_post("/api/sessions/{session_id}/queen-context", handle_queen_context)
    app.router.add_post("/api/sessions/{session_id}/pause", handle_pause)
    app.router.add_post("/api/sessions/{session_id}/resume", handle_resume)
    app.router.add_post("/api/sessions/{session_id}/stop", handle_stop)
    app.router.add_post("/api/sessions/{session_id}/cancel-queen", handle_cancel_queen)
    app.router.add_post("/api/sessions/{session_id}/replay", handle_replay)
    app.router.add_get("/api/sessions/{session_id}/goal-progress", handle_goal_progress)
    app.router.add_get("/api/projects/{project_id}/queue", handle_project_queue)

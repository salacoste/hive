"""Queen orchestrator — builds and runs the queen executor.

Extracted from SessionManager._start_queen() to keep session management
and queen orchestration concerns separate.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from framework.server.session_manager import Session

logger = logging.getLogger(__name__)


def _normalize_mcp_server_name(name: object) -> str:
    """Normalize MCP server names for alias-safe dedupe (`_` <-> `-`)."""
    return str(name or "").strip().replace("_", "-")


def _project_workspace_from_metadata(project: dict[str, Any] | None) -> str | None:
    """Resolve preferred workspace path from project metadata."""
    if not isinstance(project, dict):
        return None

    def _norm(path: object) -> str | None:
        raw = str(path or "").strip()
        if not raw:
            return None
        resolved = Path(raw).expanduser().resolve()
        return str(resolved) if resolved.exists() else None

    direct = _norm(project.get("workspace_path"))
    if direct:
        return direct

    profile = project.get("toolchain_profile")
    if isinstance(profile, dict):
        approved = profile.get("approved_plan")
        if isinstance(approved, dict):
            source = approved.get("source")
            if isinstance(source, dict):
                approved_ws = _norm(source.get("workspace_path"))
                if approved_ws:
                    return approved_ws
    return None


def _workspace_allow_paths_for_session(
    *,
    session: Session,
    session_manager: Any,
) -> list[str]:
    """Collect allowed workspace roots for coder-tools in this session."""
    paths: list[str] = []
    try:
        project = session_manager.get_project(session.project_id)
    except Exception:
        project = None

    project_workspace = _project_workspace_from_metadata(project)
    if project_workspace:
        paths.append(project_workspace)

    env_workspace_root = str(os.environ.get("HIVE_WORKSPACE_ROOT", "")).strip()
    if env_workspace_root:
        resolved = Path(env_workspace_root).expanduser().resolve()
        if resolved.exists():
            paths.append(str(resolved))

    extra = str(os.environ.get("HIVE_CODER_TOOLS_ALLOWED_PATHS", "")).strip()
    if extra:
        for part in extra.split(os.pathsep):
            raw = part.strip()
            if not raw:
                continue
            resolved = Path(raw).expanduser().resolve()
            if resolved.exists():
                paths.append(str(resolved))

    deduped: list[str] = []
    seen: set[str] = set()
    for item in paths:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _patch_mcp_server_list_for_workspace(
    *,
    server_list: list[dict[str, Any]],
    allow_paths: list[str],
) -> list[dict[str, Any]]:
    if not allow_paths:
        return server_list
    patched: list[dict[str, Any]] = []
    joined = os.pathsep.join(allow_paths)
    for server in server_list:
        current = dict(server)
        if str(current.get("name") or "") == "coder-tools":
            env = dict(current.get("env") or {})
            existing = str(env.get("CODER_TOOLS_ALLOWED_PATHS") or "").strip()
            if existing:
                env["CODER_TOOLS_ALLOWED_PATHS"] = os.pathsep.join([existing, joined])
            else:
                env["CODER_TOOLS_ALLOWED_PATHS"] = joined
            current["env"] = env
        patched.append(current)
    return patched


def _hydrate_queen_identity_prompt(*, session: Any, phase_state: Any) -> None:
    """Populate phase-state identity fields from the selected queen profile."""
    from framework.agents.queen.queen_profiles import (
        ensure_default_queens,
        format_queen_identity_prompt,
        load_queen_profile,
    )

    queen_id = str(getattr(session, "queen_name", "") or "").strip() or "queen_technology"
    try:
        ensure_default_queens()
        profile = load_queen_profile(queen_id)
    except Exception:
        logger.warning("Queen: failed to load profile for %s", queen_id, exc_info=True)
        return

    phase_state.queen_profile = profile
    phase_state.queen_identity_prompt = format_queen_identity_prompt(profile, max_examples=1)


async def create_queen(
    session: Session,
    session_manager: Any,
    worker_identity: str | None,
    queen_dir: Path,
    initial_prompt: str | None = None,
) -> asyncio.Task:
    """Build the queen executor and return the running asyncio task.

    Handles tool registration, phase-state initialization, prompt
    composition, persona hook setup, graph preparation, and the queen
    event loop.
    """
    from framework.agents.queen.agent import (
        queen_goal,
        queen_loop_config,
    )
    import framework.agents.queen.nodes as queen_nodes
    from framework.graph.executor import GraphExecutor
    from framework.orchestrator.edge import GraphSpec
    from framework.runner.mcp_registry import MCPRegistry
    from framework.runner.tool_registry import ToolRegistry
    from framework.runtime.core import Runtime
    from framework.runtime.event_bus import AgentEvent, EventType
    from framework.tools.queen_lifecycle_tools import (
        QueenPhaseState,
        register_queen_lifecycle_tools,
    )

    # Compatibility shim:
    # The queen nodes module evolved from a legacy 5-phase symbol set
    # (planning/building/staging/running/editing) to a newer 4-phase set
    # (independent/incubating/working/reviewing). Keep create_queen resilient
    # by resolving legacy symbols first, then falling back to the new names.
    def _node_attr(*names: str, default: Any) -> Any:
        for name in names:
            if hasattr(queen_nodes, name):
                return getattr(queen_nodes, name)
        return default

    _QUEEN_PLANNING_TOOLS = _node_attr("_QUEEN_PLANNING_TOOLS", "_QUEEN_INDEPENDENT_TOOLS", default=[])
    _QUEEN_BUILDING_TOOLS = _node_attr("_QUEEN_BUILDING_TOOLS", "_QUEEN_INCUBATING_TOOLS", default=[])
    _QUEEN_STAGING_TOOLS = _node_attr("_QUEEN_STAGING_TOOLS", "_QUEEN_REVIEWING_TOOLS", default=[])
    _QUEEN_RUNNING_TOOLS = _node_attr("_QUEEN_RUNNING_TOOLS", "_QUEEN_WORKING_TOOLS", default=[])
    _QUEEN_EDITING_TOOLS = _node_attr("_QUEEN_EDITING_TOOLS", "_QUEEN_REVIEWING_TOOLS", default=[])

    _queen_character_core = _node_attr("_queen_character_core", default="")
    _queen_style = _node_attr("_queen_style", default="")
    _queen_behavior_always = _node_attr("_queen_behavior_always", default="")
    _queen_role_planning = _node_attr("_queen_role_planning", "_queen_role_independent", default="")
    _queen_role_building = _node_attr("_queen_role_building", "_queen_role_incubating", default="")
    _queen_role_staging = _node_attr("_queen_role_staging", "_queen_role_reviewing", default="")
    _queen_role_running = _node_attr("_queen_role_running", "_queen_role_working", default="")
    _queen_identity_editing = _node_attr("_queen_identity_editing", "_queen_role_reviewing", default="")

    _queen_tools_planning = _node_attr("_queen_tools_planning", "_queen_tools_independent", default="")
    _queen_tools_building = _node_attr("_queen_tools_building", "_queen_tools_incubating", default="")
    _queen_tools_staging = _node_attr("_queen_tools_staging", "_queen_tools_reviewing", default="")
    _queen_tools_running = _node_attr("_queen_tools_running", "_queen_tools_working", default="")
    _queen_tools_editing = _node_attr("_queen_tools_editing", "_queen_tools_reviewing", default="")

    _queen_behavior_planning = _node_attr("_queen_behavior_planning", "_queen_behavior_independent", default="")
    _queen_behavior_building = _node_attr("_queen_behavior_building", "_queen_behavior_independent", default="")
    _queen_behavior_staging = _node_attr("_queen_behavior_staging", "_queen_behavior_independent", default="")
    _queen_behavior_running = _node_attr("_queen_behavior_running", "_queen_behavior_independent", default="")
    _queen_behavior_editing = _node_attr("_queen_behavior_editing", "_queen_behavior_independent", default="")

    _planning_knowledge = _node_attr("_planning_knowledge", "_queen_memory_instructions", default="")
    _shared_building_knowledge = _node_attr("_shared_building_knowledge", "_queen_memory_instructions", default="")
    _building_knowledge = _node_attr("_building_knowledge", default="")
    _queen_phase_7 = _node_attr("_queen_phase_7", default="")
    _appendices = _node_attr("_appendices", default="")
    queen_node = _node_attr("queen_node", default=None)

    hive_home = Path.home() / ".hive"

    # ---- Tool registry ------------------------------------------------
    queen_registry = ToolRegistry()
    import framework.agents.queen as _queen_pkg

    queen_pkg_dir = Path(_queen_pkg.__file__).parent
    mcp_config = queen_pkg_dir / "mcp_servers.json"
    loaded_from_config: set[str] = set()
    if mcp_config.exists():
        try:
            with open(mcp_config, encoding="utf-8") as f:
                config = json.load(f)
            server_list = config.get("servers", [])
            if not server_list and "servers" not in config:
                server_list = [{"name": name, **cfg} for name, cfg in config.items()]
            allow_paths = _workspace_allow_paths_for_session(
                session=session,
                session_manager=session_manager,
            )
            if allow_paths:
                server_list = _patch_mcp_server_list_for_workspace(
                    server_list=server_list,
                    allow_paths=allow_paths,
                )
                logger.info(
                    "Queen: coder-tools extra allowed roots for project '%s': %s",
                    session.project_id,
                    allow_paths,
                )
            resolved_server_list = [
                queen_registry._resolve_mcp_server_config(server_config, mcp_config.parent)
                for server_config in server_list
            ]
            loaded_from_config = {
                _normalize_mcp_server_name(server.get("name"))
                for server in resolved_server_list
                if str(server.get("name") or "").strip()
            }
            queen_registry.load_registry_servers(
                resolved_server_list,
                log_summary=False,
                preserve_existing_tools=True,
                log_collisions=False,
            )
            logger.info("Queen: loaded MCP tools from %s", mcp_config)
        except Exception:
            logger.warning("Queen: MCP config failed to load", exc_info=True)

    try:
        registry = MCPRegistry()
        registry.initialize()
        # Ensure built-in local MCP servers are present in fresh environments
        # (notably Docker) before resolving mcp_registry.json selections.
        if hasattr(registry, "ensure_defaults"):
            try:
                registry.ensure_defaults()
            except Exception:
                logger.debug("Queen: MCP ensure_defaults failed", exc_info=True)
        if (queen_pkg_dir / "mcp_registry.json").is_file():
            queen_registry.set_mcp_registry_agent_path(queen_pkg_dir)
        registry_configs, selection_max_tools = registry.load_agent_selection(queen_pkg_dir)
        if registry_configs:
            # Avoid loading the same server twice when both static mcp_servers.json and
            # registry selection reference it (including underscore/dash aliases).
            filtered_registry_configs: list[dict[str, Any]] = []
            skipped_registry_names: list[str] = []
            for server in registry_configs:
                raw_name = str(server.get("name") or "").strip()
                norm_name = _normalize_mcp_server_name(raw_name)
                if norm_name and norm_name in loaded_from_config:
                    skipped_registry_names.append(raw_name)
                    continue
                filtered_registry_configs.append(server)
            if skipped_registry_names:
                logger.info(
                    "Queen: skipped duplicate MCP registry servers already loaded from mcp_servers.json: %s",
                    sorted(set(skipped_registry_names)),
                )
            registry_configs = filtered_registry_configs
        if registry_configs:
            results = queen_registry.load_registry_servers(
                registry_configs,
                preserve_existing_tools=True,
                log_collisions=True,
                max_tools=selection_max_tools,
            )
            logger.info("Queen: loaded MCP registry servers: %s", results)
    except Exception:
        logger.warning("Queen: MCP registry config failed to load", exc_info=True)

    # ---- Phase state --------------------------------------------------
    initial_phase = "staging" if worker_identity else "planning"
    phase_state = QueenPhaseState(phase=initial_phase, event_bus=session.event_bus)
    session.phase_state = phase_state
    _hydrate_queen_identity_prompt(session=session, phase_state=phase_state)

    # ---- Track ask rounds during planning ----------------------------
    # Increment planning_ask_rounds each time the queen requests user
    # input (ask_user or ask_user_multiple) while in the planning phase.
    async def _track_planning_asks(event: AgentEvent) -> None:
        if phase_state.phase != "planning":
            return
        # Only count explicit ask_user / ask_user_multiple calls, not
        # auto-block (text-only turns emit CLIENT_INPUT_REQUESTED with
        # an empty prompt and no options/questions).
        data = event.data or {}
        has_prompt = bool(data.get("prompt"))
        has_questions = bool(data.get("questions"))
        has_options = bool(data.get("options"))
        if has_prompt or has_questions or has_options:
            phase_state.planning_ask_rounds += 1

    session.event_bus.subscribe(
        [EventType.CLIENT_INPUT_REQUESTED],
        _track_planning_asks,
        filter_stream="queen",
    )

    # ---- Lifecycle tools (always registered) --------------------------
    register_queen_lifecycle_tools(
        queen_registry,
        session=session,
        session_id=session.id,
        session_manager=session_manager,
        manager_session_id=session.id,
        phase_state=phase_state,
    )

    # ---- Monitoring tools (only when worker is loaded) ----------------
    if session.graph_runtime:
        from framework.tools.worker_monitoring_tools import register_worker_monitoring_tools

        register_worker_monitoring_tools(
            queen_registry,
            session.worker_path,
            worker_graph_id=session.graph_runtime._graph_id,
            default_session_id=session.id,
        )

    queen_tools = list(queen_registry.get_tools().values())
    queen_tool_executor = queen_registry.get_executor()

    # ---- Partition tools by phase ------------------------------------
    planning_names = set(_QUEEN_PLANNING_TOOLS)
    building_names = set(_QUEEN_BUILDING_TOOLS)
    staging_names = set(_QUEEN_STAGING_TOOLS)
    running_names = set(_QUEEN_RUNNING_TOOLS)
    editing_names = set(_QUEEN_EDITING_TOOLS)

    registered_names = {t.name for t in queen_tools}
    missing_building = building_names - registered_names
    if missing_building:
        logger.warning(
            "Queen: %d/%d building tools NOT registered: %s",
            len(missing_building),
            len(building_names),
            sorted(missing_building),
        )
    logger.info("Queen: registered tools: %s", sorted(registered_names))

    phase_state.planning_tools = [t for t in queen_tools if t.name in planning_names]
    phase_state.building_tools = [t for t in queen_tools if t.name in building_names]
    phase_state.staging_tools = [t for t in queen_tools if t.name in staging_names]
    phase_state.running_tools = [t for t in queen_tools if t.name in running_names]
    phase_state.editing_tools = [t for t in queen_tools if t.name in editing_names]

    # ---- Cross-session memory ----------------------------------------
    from framework.agents.queen.queen_memory_v2 import (
        colony_memory_dir,
        global_memory_dir,
        init_memory_dir,
    )

    colony_dir = colony_memory_dir(session.id)
    global_dir = global_memory_dir()
    init_memory_dir(colony_dir, migrate_legacy=True)
    init_memory_dir(global_dir)
    phase_state.global_memory_dir = global_dir

    # Keep global recall cache fresh on real user input events.
    async def _recall_on_user_input(event: AgentEvent) -> None:
        content = (event.data or {}).get("content", "")
        if not content or not isinstance(content, str):
            return
        try:
            from framework.agents.queen.recall_selector import (
                format_recall_injection,
                select_memories,
            )

            selected = await select_memories(content, session.llm, global_dir)
            phase_state._cached_global_recall_block = format_recall_injection(
                selected,
                global_dir,
                heading="Global Memories",
            )
        except Exception:
            logger.debug("recall: user-turn cache update failed", exc_info=True)

    session.event_bus.subscribe(
        [EventType.CLIENT_INPUT_RECEIVED],
        _recall_on_user_input,
        filter_stream="queen",
    )

    # ---- Compose phase-specific prompts ------------------------------
    _orig_node = queen_node

    if worker_identity is None:
        worker_identity = (
            "\n\n# Worker Profile\n"
            "No worker agent loaded. You are operating independently.\n"
            "Design or build the agent to solve the user's problem "
            "according to your current phase."
        )

    _planning_body = (
        _queen_character_core
        + _queen_role_planning
        + _queen_style
        + _shared_building_knowledge
        + _queen_tools_planning
        + _queen_behavior_always
        + _queen_behavior_planning
        + _planning_knowledge
        + worker_identity
    )
    phase_state.prompt_planning = _planning_body

    _building_body = (
        _queen_character_core
        + _queen_role_building
        + _queen_style
        + _shared_building_knowledge
        + _queen_tools_building
        + _queen_behavior_always
        + _queen_behavior_building
        + _building_knowledge
        + _queen_phase_7
        + _appendices
        + worker_identity
    )
    phase_state.prompt_building = _building_body
    phase_state.prompt_staging = (
        _queen_character_core
        + _queen_role_staging
        + _queen_style
        + _queen_tools_staging
        + _queen_behavior_always
        + _queen_behavior_staging
        + worker_identity
    )
    phase_state.prompt_running = (
        _queen_character_core
        + _queen_role_running
        + _queen_style
        + _queen_tools_running
        + _queen_behavior_always
        + _queen_behavior_running
        + worker_identity
    )
    phase_state.prompt_editing = (
        _queen_identity_editing
        + _queen_style
        + _queen_tools_editing
        + _queen_behavior_always
        + _queen_behavior_editing
        + worker_identity
    )

    # ---- Default skill protocols -------------------------------------
    _queen_skill_dirs: list[str] = []
    try:
        from framework.skills.manager import SkillsManager, SkillsManagerConfig

        # Pass project_root so user-scope skills (~/.hive/skills/, ~/.agents/skills/)
        # are discovered. Queen has no agent-specific project root, so we use its
        # own directory — the value just needs to be non-None to enable user-scope scanning.
        _queen_skills_mgr = SkillsManager(SkillsManagerConfig(project_root=Path(__file__).parent))
        _queen_skills_mgr.load()
        phase_state.protocols_prompt = _queen_skills_mgr.protocols_prompt
        phase_state.skills_catalog_prompt = _queen_skills_mgr.skills_catalog_prompt
        _queen_skill_dirs = _queen_skills_mgr.allowlisted_dirs
    except Exception:
        logger.debug("Queen skill loading failed (non-fatal)", exc_info=True)

    # ---- Graph preparation -------------------------------------------
    initial_prompt_text = phase_state.get_current_prompt()

    registered_tool_names = set(queen_registry.get_tools().keys())
    declared_tools = _orig_node.tools or []
    available_tools = [t for t in declared_tools if t in registered_tool_names]

    node_updates: dict = {
        "system_prompt": initial_prompt_text,
    }
    if set(available_tools) != set(declared_tools):
        missing_set = set(declared_tools) - registered_tool_names
        # Monitoring tools are phase-scoped: when no worker graph is loaded yet,
        # they are expected to be absent and should not pollute startup logs.
        if not session.graph_runtime:
            missing_set -= {"get_worker_health_summary"}
        missing = sorted(missing_set)
        if missing:
            logger.warning("Queen: tools not available: %s", missing)
        node_updates["tools"] = available_tools

    adjusted_node = _orig_node.model_copy(update=node_updates)
    _queen_loop_config = dict(queen_loop_config or {})
    queen_graph = GraphSpec(
        id="queen-graph",
        goal_id=queen_goal.id,
        version="1.0.0",
        entry_node=adjusted_node.id,
        entry_points={"default": adjusted_node.id},
        terminal_nodes=[],
        pause_nodes=[],
        nodes=[adjusted_node],
        edges=[],
        loop_config=_queen_loop_config,
        description="Queen runtime graph",
        created_by="system",
    )

    # ---- Queen event loop --------------------------------------------
    queen_runtime = Runtime(hive_home / "queen")

    async def _queen_loop():
        logger.debug("[_queen_loop] Starting queen loop for session %s", session.id)
        try:
            logger.debug("[_queen_loop] Creating GraphExecutor...")
            executor = GraphExecutor(
                runtime=queen_runtime,
                llm=session.llm,
                tools=queen_tools,
                tool_executor=queen_tool_executor,
                event_bus=session.event_bus,
                stream_id="queen",
                storage_path=queen_dir,
                loop_config=_queen_loop_config,
                execution_id=session.id,
                dynamic_tools_provider=phase_state.get_current_tools,
                dynamic_prompt_provider=phase_state.get_current_prompt,
                iteration_metadata_provider=lambda: {"phase": phase_state.phase},
                skill_dirs=_queen_skill_dirs,
                protocols_prompt=phase_state.protocols_prompt,
                skills_catalog_prompt=phase_state.skills_catalog_prompt,
            )
            session.queen_executor = executor
            logger.debug("[_queen_loop] GraphExecutor created and stored in session.queen_executor")

            # Wire inject_notification so phase switches notify the queen LLM
            async def _inject_phase_notification(content: str) -> None:
                node = executor.node_registry.get("queen")
                if node is not None and hasattr(node, "inject_event"):
                    await node.inject_event(content)

            phase_state.inject_notification = _inject_phase_notification

            # Auto-switch to editing when worker execution finishes.
            # The worker stays loaded — queen can tweak config and re-run.
            async def _on_worker_done(event):
                if event.stream_id == "queen":
                    return
                if phase_state.phase == "running":
                    if event.type == EventType.EXECUTION_COMPLETED:
                        # Mark worker as configured after first successful run
                        session.worker_configured = True
                        output = event.data.get("output", {})
                        output_summary = ""
                        if output:
                            for key, value in output.items():
                                val_str = str(value)
                                if len(val_str) > 200:
                                    val_str = val_str[:200] + "..."
                                output_summary += f"\n  {key}: {val_str}"
                        _out = output_summary or " (no output keys set)"
                        notification = (
                            "[WORKER_TERMINAL] Worker finished successfully.\n"
                            f"Output:{_out}\n"
                            "Report this to the user. "
                            "Ask if they want to re-run with different input "
                            "or tweak the configuration."
                        )
                    else:  # EXECUTION_FAILED
                        error = event.data.get("error", "Unknown error")
                        notification = (
                            "[WORKER_TERMINAL] Worker failed.\n"
                            f"Error: {error}\n"
                            "Report this to the user and help them troubleshoot. "
                            "You can re-run with different input or escalate to "
                            "building/planning if code changes are needed."
                        )

                    node = executor.node_registry.get("queen")
                    if node is not None and hasattr(node, "inject_event"):
                        await node.inject_event(notification)

                    await phase_state.switch_to_editing(source="auto")

            session.event_bus.subscribe(
                event_types=[EventType.EXECUTION_COMPLETED, EventType.EXECUTION_FAILED],
                handler=_on_worker_done,
            )
            session_manager._subscribe_worker_handoffs(session, executor)

            # ---- Reflection + recall memory subscriptions ----------------
            from framework.agents.queen.reflection_agent import subscribe_reflection_triggers

            _reflection_subs = await subscribe_reflection_triggers(
                session.event_bus,
                queen_dir,
                session.llm,
                global_memory_dir=global_dir,
                queen_memory_dir=colony_dir,
                queen_id=getattr(session, "queen_name", None),
            )

            # Store sub IDs on session for teardown.
            session.memory_reflection_subs = _reflection_subs

            logger.info(
                "Queen starting in %s phase with %d tools: %s",
                phase_state.phase,
                len(phase_state.get_current_tools()),
                [t.name for t in phase_state.get_current_tools()],
            )
            logger.debug("[_queen_loop] Calling executor.execute()...")
            result = await executor.execute(
                graph=queen_graph,
                goal=queen_goal,
                input_data={"greeting": initial_prompt or "Session started."},
                session_state={"resume_session_id": session.id},
            )
            logger.debug(
                "[_queen_loop] executor.execute() returned with success=%s", result.success
            )
            if result.success:
                logger.warning("Queen executor returned (should be forever-alive)")
            else:
                logger.error(
                    "Queen executor failed: %s",
                    result.error or "(no error message)",
                )
        except asyncio.CancelledError:
            logger.info("[_queen_loop] Queen loop cancelled (normal shutdown)")
            raise
        except Exception as e:
            logger.exception("[_queen_loop] Queen conversation crashed: %s", e)
            raise
        finally:
            logger.warning(
                "[_queen_loop] Queen loop exiting — clearing queen_executor for session '%s'",
                session.id,
            )
            session.queen_executor = None

    return asyncio.create_task(_queen_loop())

# 17. Memory Architecture Transition Decision (Wave 2 / Item 120)

Date: 2026-04-10

## Context

Upstream continuation delta includes a memory simplification wave that removes:

- `core/framework/agents/queen/queen_memory.py`
- `core/framework/tools/queen_memory_tools.py`
- colony reflection wiring in runtime path (`GraphContext` / `GraphExecutor` / `ExecutionStream` / `AgentRuntime` / `WorkerAgent`)
- `save_global_memory` surface from queen lifecycle tools and node instructions

In local autonomous-factory deployment these components are still part of active contracts:

- project-scoped continuity in queen sessions,
- telegram/web behavior parity,
- autonomous loop runtime assumptions,
- operator-facing memory controls.

## Decision

For Wave 2, we **defer destructive memory-architecture removals** and keep current hybrid compatibility model.

This means:

1. No file deletions for `queen_memory.py` / `queen_memory_tools.py` in this wave.
2. No removal of colony reflection runtime wiring in this wave.
3. No removal of `save_global_memory` tool surface in this wave.

## Rationale

- Current local behavior is validated around hybrid memory assumptions (queen/worker handoff + project operations).
- Upstream removal bundle is architectural, not an isolated bug fix.
- Blind merge would risk regressions in autonomous control plane and Telegram bridge workflows.

## Exit Criteria For Future Cutover

Transition may proceed only when all are satisfied:

1. Migration design approved (state mapping from old memory model to simplified model).
2. Feature-flagged rollout available (dual path or rollback toggle).
3. Dedicated regression matrix green:
   - `core/tests/test_queen_memory.py`
   - `core/framework/server/tests/test_api.py -k "sessions or autonomous or execution_template or telegram_bridge_status_endpoint or health"`
   - `core/framework/server/tests/test_telegram_bridge.py`
   - acceptance and runtime-parity gates.
4. Explicit rollback command sequence documented and rehearsal-proven.

## Rollback Plan (if transition starts and fails)

1. Revert only memory-transition commits/files.
2. Re-run:
   - `uv run --active pytest core/tests/test_queen_memory.py -q`
   - `uv run --active pytest core/framework/server/tests/test_api.py -k "sessions or autonomous or execution_template or telegram_bridge_status_endpoint or health" -q`
   - `uv run --active pytest core/framework/server/tests/test_telegram_bridge.py -q`
   - `./scripts/check_runtime_parity.sh`
3. Mark backlog item `blocked` with failure reason and exact failing contract.

## Immediate Outcome For Item 120

- High-risk transition is gated and documented.
- Production-local profile remains on validated hybrid memory path.

## Wave 4 Revalidation (April 11, 2026)

Context refresh after Wave 4 medium-risk sync (`item 154`):

- `queen_memory_v2` and runtime/event files were refreshed from upstream bucket B.
- Reflection compatibility remained required in local branch contracts
  (`reflection_agent` still expects hybrid memory orchestration behavior).

Decision remains **defer** for bucket C destructive removals:

1. Keep `core/framework/agents/queen/queen_memory.py`.
2. Keep `core/framework/tools/queen_memory_tools.py`.

Revalidation evidence:

- `docker run ... uv run pytest core/tests/test_event_bus.py core/tests/test_queen_memory.py core/tests/test_session_manager_worker_handoff.py -q` -> `83 passed`.
- Reflection-agent compatibility patch applied in local branch to align with refreshed `queen_memory_v2` API surface.

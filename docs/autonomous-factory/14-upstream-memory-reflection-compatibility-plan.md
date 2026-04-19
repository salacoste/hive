# 14. Upstream Memory/Reflection Compatibility Plan

Date: 2026-04-10  
Task: Backlog item `112` (`Queen Memory/Reflection Upstream Delta Audit + Compatibility Design`)

## Scope Audited

- Upstream wave: `6637bc8d..19469ff4`
- Primary files:
  - `core/framework/agents/queen/queen_memory_v2.py`
  - `core/framework/agents/queen/recall_selector.py`
  - `core/framework/agents/queen/reflection_agent.py`
  - `core/framework/server/queen_orchestrator.py`
  - `core/framework/server/routes_execution.py`
  - `core/framework/server/session_manager.py`
  - `core/tests/test_queen_memory.py`
  - `core/tests/test_session_manager_worker_handoff.py`

## What Upstream Changed (Observed)

1. Memory model simplified from hybrid (`colony + global`) to `global-only`.
2. `recall_selector` switched to global-only defaults and removed staleness warning injection.
3. `reflection_agent` simplified:
  - removed worker-specific reflection subscriptions;
  - removed diary update flow;
  - tightened memory types to global categories only.
4. `queen_orchestrator` now seeds/refreshes recall on `CLIENT_INPUT_RECEIVED` and subscribes reflection to global memory directory.
5. `routes_execution.handle_chat` now publishes `CLIENT_INPUT_RECEIVED` before `node.inject_event(...)`.
6. `session_manager` removes colony-memory plumbing and adds shutdown reflection spawning.

## Local System Constraints (Must Preserve)

1. Project-aware sessions and strict cross-project resume guards.
2. Autonomous pipeline + queue/concurrency controls in server routes.
3. Telegram bridge behavior (status/digest/control actions) and stable queen lifecycle.
4. Existing worker handoff behavior and session continuity.
5. No regression in containerized runtime contract.

## Compatibility Risk Matrix

1. `queen_memory_v2.py` full replace: **High risk**  
   Reason: removes colony memory + migration helpers currently used by local session manager/worker runtime.
2. `recall_selector.py` full replace: **Medium risk**  
   Reason: API and behavior shifts (schema, headings, staleness logic, active_tools filter removal).
3. `reflection_agent.py` full replace: **High risk**  
   Reason: removes worker/diary paths and changes tool-call parsing assumptions.
4. `queen_orchestrator.py` memory section only: **Medium risk**  
   Reason: intersects with local phase/runtime integrations but adds useful recall timing behavior.
5. `routes_execution.py` publish-before-inject change: **Low risk, high value**  
   Reason: deterministic recall timing; minimal surface area.
6. `session_manager.py` memory teardown/load sections: **High risk**  
   Reason: file has heavy local customizations (projects/autonomous/trigger behavior).

## Recommended Merge Strategy

### Wave A (safe, immediate)

1. Backport `routes_execution` event order fix (publish before inject).
2. Backport litellm-compatible reflection tool-call parsing improvements only (without deleting local colony support).
3. Add shutdown reflection spawning pattern in `session_manager` with strong task references.

### Wave B (controlled hybrid)

1. Keep local hybrid memory architecture (`colony + global`) for now.
2. Introduce compatibility flag:
   - `HIVE_MEMORY_MODE=hybrid` (default, current behavior),
   - `HIVE_MEMORY_MODE=global_only` (upstream target mode).
3. Implement upstream global-only constraints under `global_only` mode while retaining legacy paths for `hybrid`.

### Wave C (final convergence)

1. Migrate tests and runtime to `global_only`.
2. Remove colony memory code paths only after:
   - worker handoff regression suite stays green,
   - autonomous and Telegram smoke tests pass,
   - runtime parity checks pass in container.

## Rollback Plan

1. Roll back by toggling `HIVE_MEMORY_MODE=hybrid`.
2. If needed, revert only memory/reflection files (no project/autonomous files).
3. Keep API contract unchanged for project/autonomous endpoints during memory migration.

## Acceptance Gate For Item 113

1. `core/tests/test_queen_memory.py` green (updated hybrid/global compatibility assertions).
2. `core/tests/test_session_manager_worker_handoff.py` green.
3. `core/framework/server/tests/test_api.py -k "sessions or autonomous or execution_template"` green.
4. `core/framework/server/tests/test_telegram_bridge.py` green.
5. `scripts/check_runtime_parity.sh` green in container runtime.

## Decision

For backlog item `113`, merge only the compatible subset from upstream memory wave:

1. event ordering + recall timing improvements,
2. reflection robustness improvements,
3. shutdown reflection reliability,

while explicitly deferring full global-only memory cutover until dedicated migration gating is complete.

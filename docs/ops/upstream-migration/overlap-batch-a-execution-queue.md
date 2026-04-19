# Overlap Batch A Execution Queue

Date: 2026-04-18

Source:
- `docs/ops/upstream-migration/overlap-batch-a-conflict-probe-latest.md`
- `docs/ops/upstream-migration/overlap-batch-a-integration-probe-latest.md`
- `docs/ops/upstream-migration/overlap-batch-a-landing-rehearsal-latest.md`

## Conflict Queue (ordered)

1. `core/framework/server/app.py`
2. `core/framework/server/routes_execution.py`
3. `core/framework/server/routes_sessions.py`
4. `core/framework/server/session_manager.py`
5. `core/framework/server/queen_orchestrator.py`

## Why this order

1. `app.py` is route wiring root (must expose project/autonomous/telegram hooks first).
2. `routes_execution.py` and `routes_sessions.py` depend on app keys/session contracts.
3. `session_manager.py` consolidates session/project lifecycle semantics.
4. `queen_orchestrator.py` finalizes project workspace propagation after session path stabilizes.

## Per-file checkpoints

1. After `app.py` merge:
   - `uv run --package framework pytest core/framework/server/tests/test_api.py -k "health or telegram_bridge_status_endpoint" -q`
2. After `routes_execution.py` and `routes_sessions.py`:
   - `uv run --package framework pytest core/framework/server/tests/test_api.py -k "sessions or queue or project" -q`
3. After `session_manager.py`:
   - `uv run --package framework pytest core/framework/server/tests/test_api.py -k "sessions" -q`
4. After `queen_orchestrator.py`:
   - `uv run --package framework pytest core/framework/server/tests/test_queen_orchestrator.py -q`
5. End-to-end batch validation:
   - `uv run --package framework pytest core/framework/server/tests/test_api.py -q`
   - `uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q`

## Merge policy

1. Do not apply full-file overlay from `overlap-batch-a-latest.patch`.
2. Use focus map + focus patch to port only activation-critical hunks.
3. Keep each file merge in a separate commit for rollback granularity.

## Dependency Closure Prerequisite

1. Batch A server patch is not runnable on `origin/main` by itself.
2. Baseline integration probe fails on missing package surface:
   - `ModuleNotFoundError: framework.runtime`.
3. Mergeable compatibility fix implemented:
   - `core/framework/runner/__init__.py` switched to lazy runner exports
     (`AgentRunner/AgentInfo/ValidationResult`) to prevent package-init cycle.
4. Overlay (`runtime + graph + runner + routes_graphs.py`) now passes:
   - app smoke (`create_app` + route checks) = `ok`;
   - API health pytest = `ok`.
5. Before landing-branch apply, include coherent runtime/graph/runner slice together with the
   runner lazy-export fix.
6. Use dependency bundle artifact for deterministic apply:
   - `docs/ops/upstream-migration/overlap-batch-a-dependency-bundle-latest.md`.
7. Use hotspots bundle for coherent server file overlay on landing branch:
   - `docs/ops/upstream-migration/overlap-batch-a-hotspots-bundle-latest.md`.
   - apply helper: `scripts/upstream_overlap_batch_a_bundle_apply.sh`.
8. Validate with landing rehearsal gate profile:
   - `test_api.py` profile subset (`health/session/execution/credentials`, excludes
     `worker_input_route_removed` path-shape check),
   - `test_telegram_bridge.py`,
   - `test_queen_orchestrator.py`.

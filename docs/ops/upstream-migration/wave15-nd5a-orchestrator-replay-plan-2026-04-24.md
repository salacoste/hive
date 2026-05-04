# Wave 15 — ND-5A Orchestrator Micro-Lane Replay Plan

Date: 2026-04-24
Status: ready for execution

## Scope

- `core/framework/orchestrator/client_io.py`
- `core/framework/orchestrator/gcu.py`
- `core/framework/orchestrator/node.py`
- `core/framework/orchestrator/safe_eval.py`

Patch artifact:

- `docs/ops/upstream-migration/wave15-nd5a-orchestrator.patch`

Probe artifact:

- `docs/ops/upstream-migration/wave15-nd5a-orchestrator-probe-2026-04-24.json`

Probe summary:

- `git apply --check` passed (`exit_code=0`).

## Execution checklist

1. Apply patch:
   - `git apply docs/ops/upstream-migration/wave15-nd5a-orchestrator.patch`
2. Run targeted checks:
   - `uv run pytest core/tests/test_event_loop_node.py core/tests/test_safe_eval.py core/tests/test_node_conversation.py -q`
3. Run full regression gate:
   - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
4. Record execution artifact and update backlog/docs.

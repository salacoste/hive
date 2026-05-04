# Wave 15 ND-5D Replay Plan (Event publishing)

Date: 2026-04-25

Scope:
- `core/framework/agent_loop/internals/event_publishing.py`

Goal:
- Reconcile `publish_llm_turn_complete(...)` signature/payload metadata fields (`cache_creation_tokens`, `cost_usd`) with upstream.

Artifacts:
- `docs/ops/upstream-migration/wave15-nd5d-event-publishing.patch`
- `docs/ops/upstream-migration/wave15-nd5d-event-publishing-probe-2026-04-25.json`

Validation plan:
1. Targeted:
- `uv run pytest core/tests/test_event_loop_node.py core/tests/test_node_conversation.py -q`
2. Full gate:
- `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`

Exit criteria:
- replay applied or explicitly reconciled,
- validations green,
- execution artifact added,
- backlog moved to next lane.

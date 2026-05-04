# Wave 15 ND-5E Replay Plan (Agent-loop types)

Date: 2026-04-25

Scope:
- `core/framework/agent_loop/types.py`
- `core/framework/agent_loop/internals/types.py`

Goal:
- Reconcile AgentLoop dynamic prompt/catalog provider metadata fields and LoopConfig hybrid compaction buffer ratio docs/defaults with upstream.

Artifacts:
- `docs/ops/upstream-migration/wave15-nd5e-agentloop-types.patch`
- `docs/ops/upstream-migration/wave15-nd5e-agentloop-types-probe-2026-04-25.json`

Validation plan:
1. Targeted:
- `uv run pytest core/tests/test_event_loop_node.py core/tests/test_node_conversation.py -q`
2. Full gate:
- `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`

Exit criteria:
- replay applied,
- targeted/full checks green,
- execution artifact added,
- backlog moved to next lane.

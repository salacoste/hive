# Wave 15 ND-5C Replay Plan (Agent-loop prompting)

Date: 2026-04-25

Scope:
- `core/framework/agent_loop/prompting.py`

Goal:
- Restore upstream-compatible dynamic skills catalog provider path in `build_prompt_spec(...)`.

Artifacts:
- `docs/ops/upstream-migration/wave15-nd5c-agentloop-prompting.patch`
- `docs/ops/upstream-migration/wave15-nd5c-agentloop-prompting-probe-2026-04-25.json`

Validation plan:
1. Targeted:
- `uv run pytest core/tests/test_event_loop_node.py core/tests/test_node_conversation.py -q`
2. Full gate:
- `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`

Exit criteria:
- replay applied,
- validations green,
- execution artifact added,
- backlog moved to next lane.

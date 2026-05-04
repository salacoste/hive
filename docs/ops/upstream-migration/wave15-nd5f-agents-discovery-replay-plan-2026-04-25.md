# Wave 15 ND-5F Replay Plan (Agents discovery)

Date: 2026-04-25

Scope:
- `core/framework/agents/discovery.py`

Goal:
- Reconcile agent discovery metadata fields (`created_at`, `icon`) and metadata fallback timestamp behavior with upstream.

Artifacts:
- `docs/ops/upstream-migration/wave15-nd5f-agents-discovery.patch`
- `docs/ops/upstream-migration/wave15-nd5f-agents-discovery-probe-2026-04-25.json`

Validation plan:
1. Targeted:
- `uv run --package framework pytest core/framework/server/tests/test_api.py -k "org or colony or queen" -q`
2. Full gate:
- `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`

Exit criteria:
- replay applied,
- targeted/full checks green,
- execution artifact added,
- backlog moved to next lane.

# Wave 15 — ND-4C3 Queen + LLM Replay Plan

Date: 2026-04-24
Status: ready for reconcile execution

## Scope

- `core/framework/agents/queen/incubating_evaluator.py`
- `core/framework/agents/queen/mcp_servers.json`
- `core/framework/agents/queen/nodes/__init__.py`
- `core/framework/agents/queen/queen_memory_v2.py`
- `core/framework/agents/queen/queen_profiles.py`
- `core/framework/agents/queen/queen_tools_config.py`
- `core/framework/agents/queen/queen_tools_defaults.py`
- `core/framework/agents/queen/recall_selector.py`
- `core/framework/agents/queen/reflection_agent.py`
- `core/framework/llm/antigravity.py`
- `core/framework/llm/litellm.py`
- `core/framework/llm/mock.py`
- `core/framework/llm/model_catalog.json`
- `core/framework/llm/provider.py`
- `core/framework/llm/stream_events.py`

Patch artifact:

- `docs/ops/upstream-migration/wave15-nd4c3-queen-llm.patch`

Probe artifact:

- `docs/ops/upstream-migration/wave15-nd4c3-queen-llm-probe-2026-04-24.json`

Probe summary:

- `git apply --check` failed (`exit_code=1`) on:
  - `core/framework/agents/queen/nodes/__init__.py`
  - `core/framework/llm/litellm.py`

Execution mode:

- Reconcile required:
  - upstream-direct for clean files;
  - three-way merge for overlapping files;
  - manual conflict resolution for the two blocked files above.

## Execution checklist

1. Apply clean file set first (or three-way merge all scope files).
2. Resolve conflicts in `queen/nodes/__init__.py` and `llm/litellm.py` preserving local proxy/runtime guardrails.
3. Run targeted checks:
   - `uv run pytest core/tests/test_litellm_provider.py core/tests/test_litellm_streaming.py core/tests/test_queen_nodes_prompt.py core/tests/test_queen_memory.py core/tests/test_trigger_fires_into_queen.py -q`
4. Run mandatory full regression gate:
   - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
5. Record ND-4C3 execution artifact and update backlog/docs.

# Wave 15 Post-ND5F Residual Triage (2026-04-25)

## Snapshot

Source artifact:
- `docs/ops/upstream-migration/wave15-post-nd5f-residual-inventory-2026-04-25.json`

Current residual (`working_tree` vs `upstream/main`):
- all records: `459`
- non-destructive: `422`
- status split: `A=352`, `M=67`, `R100=3`
- top prefixes:
  - `scripts`: `166`
  - `core`: `135`
  - `docs`: `92`
  - `(root)`: `10`
  - `tools`: `8`

## Core/Framework residual focus

`core/framework` residual summary:
- total: `108`
- modified: `28`
- added: `77`
- renamed: `3`

Modified list kept for wave planning:
- `core/framework/agent_loop/agent_loop.py`
- `core/framework/agent_loop/conversation.py`
- `core/framework/agent_loop/internals/compaction.py`
- `core/framework/agent_loop/internals/cursor_persistence.py`
- `core/framework/agent_loop/internals/synthetic_tools.py`
- `core/framework/agents/queen/mcp_registry.json`
- `core/framework/agents/queen/queen_memory_v2.py`
- `core/framework/config.py`
- `core/framework/host/event_bus.py`
- `core/framework/llm/litellm.py`
- `core/framework/loader/cli.py`
- `core/framework/loader/mcp_client.py`
- `core/framework/loader/mcp_registry.py`
- `core/framework/loader/tool_registry.py`
- `core/framework/server/README.md`
- `core/framework/server/app.py`
- `core/framework/server/queen_orchestrator.py`
- `core/framework/server/routes_config.py`
- `core/framework/server/routes_credentials.py`
- `core/framework/server/routes_execution.py`
- `core/framework/server/routes_logs.py`
- `core/framework/server/routes_messages.py`
- `core/framework/server/routes_queens.py`
- `core/framework/server/routes_sessions.py`
- `core/framework/server/session_manager.py`
- `core/framework/server/tests/test_api.py`
- `core/framework/server/tests/test_queen_orchestrator.py`
- `core/framework/tools/queen_lifecycle_tools.py`

## Triage decisions

1. Keep-local divergence (do not replay blindly from upstream):
- App-key harmonization and container-first server wiring in:
  - `core/framework/server/routes_config.py`
  - `core/framework/server/routes_messages.py`
  - `core/framework/loader/cli.py`
  - `core/framework/server/routes_logs.py`
- MCP default naming compatibility in:
  - `core/framework/loader/mcp_registry.py`
  - `core/framework/agents/queen/mcp_registry.json`
- local production routing/token model behavior in:
  - `core/framework/config.py`
  - `core/framework/host/event_bus.py`

2. High-risk residual lanes (defer to dedicated wave):
- Runtime/session complex files:
  - `core/framework/server/session_manager.py`
  - `core/framework/server/routes_sessions.py`
  - `core/framework/server/queen_orchestrator.py`
- LLM/provider heavy file:
  - `core/framework/llm/litellm.py`
- Wide contract test surface:
  - `core/framework/server/tests/test_api.py`

3. Next bounded lane selection:
- `Wave16-R1`: residual governance lane
  - establish explicit keep-local allowlist for above intentional divergences;
  - separate replay candidates from protected local behavior before any apply.

## Validation baseline

Regression gate baseline for handoff:
- `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
- expected summary: `ok=7 failed=0`

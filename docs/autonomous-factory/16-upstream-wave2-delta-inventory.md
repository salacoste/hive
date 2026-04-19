# 16. Upstream Wave 2 Delta Inventory

Date: 2026-04-10

## Goal

Build a concrete second upstream integration wave after `109..116`, using explicit risk buckets and bounded merge batches.

## Baseline Snapshot

Commands:

```bash
git rev-list --left-right --count HEAD...origin/main
git diff --name-status HEAD..origin/main
git diff --numstat HEAD..origin/main
```

Observed on April 10, 2026:

- Commit delta: `0 25` (local branch is behind upstream by 25 commits)
- File delta: 36 changed paths across framework/runtime/docs/tools/tests

## Already Integrated In `109..116`

These upstream deltas were already merged in controlled mode:

- `core/framework/graph/safe_eval.py`
- `core/tests/test_safe_eval.py`
- `core/framework/llm/litellm.py`
- `core/tests/test_litellm_provider.py`
- `tools/src/aden_tools/credentials/__init__.py`
- `tools/src/aden_tools/credentials/wandb.py`
- `tools/src/aden_tools/tools/__init__.py`
- `tools/src/aden_tools/tools/wandb_tool/*`
- `tools/tests/tools/test_wandb_tool.py`
- `core/framework/agents/queen/reflection_agent.py`
- `core/framework/server/queen_orchestrator.py`
- `core/framework/server/routes_execution.py`
- `core/framework/server/session_manager.py`
- `core/frontend/src/pages/workspace.tsx`
- `core/tests/test_session_manager_worker_handoff.py`

## Remaining Delta Buckets

### Bucket A: Low-Risk Docs/Meta Sync

- `.gitignore`
- `README.md`
- `core/framework/runtime/README.md`
- `docs/browser-extension-setup.html`
- `docs/configuration.md`
- `docs/developer-guide.md`
- `docs/environment-setup.md`

Why low risk:

- no runtime behavior change;
- docs-only or ignore-list updates;
- can be validated by lint/sanity checks.

### Bucket B: Medium-Risk Runtime/Graph Changes

- `core/framework/agents/queen/nodes/__init__.py`
- `core/framework/agents/queen/queen_memory_v2.py`
- `core/framework/agents/queen/recall_selector.py`
- `core/framework/graph/context.py`
- `core/framework/graph/executor.py`
- `core/framework/graph/worker_agent.py`
- `core/framework/runtime/agent_runtime.py`
- `core/framework/runtime/execution_stream.py`
- `core/framework/tools/queen_lifecycle_tools.py`
- `core/tests/test_event_bus.py`
- `core/tests/test_queen_memory.py`

Why medium risk:

- touches runtime/event flow and memory behavior;
- can affect project/session isolation and orchestration contracts.

### Bucket C: High-Risk Removals / Architecture Shift

- `core/framework/agents/queen/queen_memory.py` (deleted upstream)
- `core/framework/tools/queen_memory_tools.py` (deleted upstream)

Why high risk:

- upstream migrated toward simplified memory architecture;
- local autonomous factory currently relies on hybrid compatibility paths;
- requires explicit design decision and rollback path.

## Wave 2 Execution Sequence

1. Merge Bucket A completely (`118`) and keep behavior unchanged.
2. Merge Bucket B in controlled slices (`119`) with targeted tests after each slice.
3. Evaluate Bucket C behind explicit policy decision (`120`), no blind delete.
4. Run full regression gate (`121`) and update governance evidence.

## Guardrails

- Keep `project_id` and session isolation unchanged.
- Keep autonomous endpoints and scheduler contracts unchanged.
- Keep Telegram bridge behavior unchanged.
- Keep Docker runtime parity (`local` vs `hive-core`) green after each slice.

# Wave16-R3 Server/Orchestrator Test-Contract Triage (2026-04-25)

## Scope

- `core/framework/server/tests/test_queen_orchestrator.py`
- related runtime entrypoint: `core/framework/server/queen_orchestrator.py`

## Inputs

- upstream version:
  - `git show upstream/main:core/framework/server/tests/test_queen_orchestrator.py`
- local diff:
  - `git diff upstream/main -- core/framework/server/tests/test_queen_orchestrator.py`

## Findings

1. Upstream test contract is legacy and no longer API-compatible locally.
- Upstream test calls `create_queen(..., queen_profile=..., initial_phase=..., tool_registry=...)`.
- Local `create_queen` signature is now:
  - `create_queen(session, session_manager, worker_identity, queen_dir, initial_prompt=None)`.

2. Local test contract is narrow and currently covers helper behavior only.
- Local tests validate:
  - `_project_workspace_from_metadata(...)`
  - `_patch_mcp_server_list_for_workspace(...)`
- command:
  - `uv run --package framework pytest core/framework/server/tests/test_queen_orchestrator.py -q`
  - result: `3 passed`.

3. Direct runtime probe for `create_queen(...)` currently fails import wiring in local tree.
- probe script (`uv run python ...`) raised:
  - `ImportError: cannot import name '_QUEEN_BUILDING_TOOLS' from framework.agents.queen.nodes`
- implication:
  - restoring upstream legacy identity test is not executable as-is until queen node exports/import contract is reconciled.

## Decision

- `Wave16-R3` execution mode: `reconcile_only` (no replay apply from upstream test file).
- keep local test file as active contract for workspace-path and coder-tools env patch logic.
- open next bounded lane for runtime import-contract reconciliation before expanding orchestrator tests.

## Proposed next bounded lane

- `Wave16-R4`: queen orchestrator import-contract reconcile
- initial scope:
  - `core/framework/server/queen_orchestrator.py`
  - `core/framework/agents/queen/nodes/__init__.py`
  - `core/framework/agents/queen/queen_tools_defaults.py` (if needed by reconcile)
- success criteria:
  - `create_queen(...)` probe can initialize and cancel cleanly in test harness;
  - add one regression test that validates current identity/profile prompt composition path (non-legacy API).

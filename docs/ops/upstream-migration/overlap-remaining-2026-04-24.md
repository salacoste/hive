# Overlap Remaining Matrix (Wave 13, item 257)

Date: 2026-04-24

Goal: classify the 20 overlap files after Batch A/B and define bounded next slices.

## Current state

- fully synced:
  - `tools/src/aden_tools/credentials/__init__.py`
  - `core/framework/agents/queen/nodes/__init__.py`
  - `core/framework/server/routes_execution.py`
  - `core/framework/tools/queen_lifecycle_tools.py`
- partially synced (intentional local compatibility delta):
  - `tools/src/aden_tools/tools/__init__.py`
- still delta:
  - 16 files

## Candidate slices

### Slice C (attempted on 2026-04-24)

1. `core/tests/test_session_manager_worker_handoff.py`
2. `core/frontend/src/components/ChatPanel.tsx`
3. `core/framework/agents/queen/nodes/__init__.py`

Result:
- applied:
  - `core/framework/agents/queen/nodes/__init__.py`
- deferred (failed compatibility gates):
  - `core/tests/test_session_manager_worker_handoff.py`
    - reason: upstream test imports `install_worker_escalation_routing` from
      `framework.server.queen_orchestrator`, symbol absent in current local runtime.
  - `core/frontend/src/components/ChatPanel.tsx`
    - reason: upstream version drops local `clientMessageId` shape and changes
      question-widget callback contract; frontend build fails against current local pages.

Validation evidence:
- `./scripts/hive_ops_run.sh uv run pytest core/tests/test_session_manager_worker_handoff.py -q`
  - upstream replay: import error;
  - reverted to local: `9 passed`.
- `./scripts/hive_ops_run.sh bash -lc 'cd core/frontend && npm run build'`
  - upstream replay for `ChatPanel.tsx`: TypeScript contract failures;
  - reverted to local: build success.
- `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -k "execution_template or autonomous" -q`
  - after applying `queen/nodes`: `63 passed`.

### Slice D (clean but high churn, attempted on 2026-04-24)

1. `core/framework/server/routes_execution.py`
2. `core/framework/tools/queen_lifecycle_tools.py`

Notes:
- both were clean but had heavy upstream/local churn and high blast radius.

Result:
- applied:
  - `core/framework/server/routes_execution.py`
  - `core/framework/tools/queen_lifecycle_tools.py`

Validation evidence:
- `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -k "execution_template or autonomous" -q`
  - after each file: `63 passed, 130 deselected`;
- `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q`
  - `46 passed`.

### Deferred (dirty worktree or hotspot coupling)

1. `core/framework/llm/litellm.py`
2. `core/framework/server/app.py`
3. `core/framework/server/queen_orchestrator.py`
4. `core/framework/server/routes_credentials.py`
5. `core/framework/server/routes_sessions.py`
6. `core/framework/server/session_manager.py`
7. `core/framework/server/tests/test_api.py`
8. `core/frontend/src/api/execution.ts`
9. `core/frontend/src/lib/chat-helpers.ts`
10. `core/frontend/src/lib/chat-helpers.test.ts`
11. `core/frontend/src/pages/colony-chat.tsx`
12. `core/frontend/src/pages/queen-dm.tsx`
13. `core/tests/test_litellm_provider.py`
14. `core/tests/test_session_manager_worker_handoff.py`
15. `core/frontend/src/components/ChatPanel.tsx`

Reasons:
- file currently has local edits in working tree and/or strong coupling to local Telegram/WebUI/autonomous patches;
- for items 14-15: upstream replay attempted and reverted due explicit compatibility failures (documented above);
- replay to be done only via isolated patch bundles with regression gate.

## Validation requirements for next slice

1. `./scripts/hive_ops_run.sh uv run pytest core/tests/test_session_manager_worker_handoff.py -q`
2. `./scripts/hive_ops_run.sh bash -lc 'cd core/frontend && npm run test -- src/lib/chat-helpers.test.ts src/api/sessions.test.ts src/api/ops.test.ts'`
3. `./scripts/hive_ops_run.sh bash -lc 'cd core/frontend && npm run build'`

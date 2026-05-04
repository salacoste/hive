# Wave 15 — ND-3C Productivity Providers Replay Plan

Date: 2026-04-24
Status: executed (gate green)

## Scope

Provider-heavy tool files (`6`):

- `tools/src/aden_tools/tools/calendar_tool/calendar_tool.py`
- `tools/src/aden_tools/tools/github_tool/github_tool.py`
- `tools/src/aden_tools/tools/gmail_tool/gmail_tool.py`
- `tools/src/aden_tools/tools/google_docs_tool/google_docs_tool.py`
- `tools/src/aden_tools/tools/google_sheets_tool/google_sheets_tool.py`
- `tools/tests/tools/test_github_tool.py`

## Probe baseline

- patch: `docs/ops/upstream-migration/wave15-nd3c-productivity.patch`
- probe: `docs/ops/upstream-migration/wave15-nd3c-productivity-probe-2026-04-24.json`
- `git apply --check` result: pass (`exit_code=0`)

## Execution checklist

1. Apply patch:
   - `git apply docs/ops/upstream-migration/wave15-nd3c-productivity.patch`
2. Run bounded tests:
   - `uv run --package tools pytest tools/tests/tools/test_github_tool.py -q`
3. Run mandatory full gate:
   - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
4. Record execution artifact + update backlog focus.

## Execution result

- ND-3C patch replay executed successfully for all `6` scoped files;
- targeted provider test result:
  - `uv run --package tools pytest tools/tests/tools/test_github_tool.py -q`
  - `38 passed`;
- full regression gate result:
  - `ok=7 failed=0`;
- evidence artifact:
  - `docs/ops/upstream-migration/wave15-nd3c-execution-2026-04-24.json`.

## Rollback checklist

If gate fails before commit:

1. Restore only ND-3C files:
   - `git restore --worktree --staged -- tools/src/aden_tools/tools/calendar_tool/calendar_tool.py`
   - `git restore --worktree --staged -- tools/src/aden_tools/tools/github_tool/github_tool.py`
   - `git restore --worktree --staged -- tools/src/aden_tools/tools/gmail_tool/gmail_tool.py`
   - `git restore --worktree --staged -- tools/src/aden_tools/tools/google_docs_tool/google_docs_tool.py`
   - `git restore --worktree --staged -- tools/src/aden_tools/tools/google_sheets_tool/google_sheets_tool.py`
   - `git restore --worktree --staged -- tools/tests/tools/test_github_tool.py`
2. Re-run smoke gate:
   - `./scripts/upstream_sync_regression_gate.sh`

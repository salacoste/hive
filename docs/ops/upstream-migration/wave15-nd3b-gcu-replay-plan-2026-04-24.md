# Wave 15 — ND-3B GCU/Browser Replay Plan

Date: 2026-04-24
Status: executed (gate green)

## Scope

GCU/browser runtime files (`7`):

- `tools/src/gcu/__init__.py`
- `tools/src/gcu/browser/__init__.py`
- `tools/src/gcu/browser/bridge.py`
- `tools/src/gcu/browser/tools/inspection.py`
- `tools/src/gcu/browser/tools/interactions.py`
- `tools/src/gcu/browser/tools/tabs.py`
- `tools/tests/test_browser_tools_comprehensive.py`

## Probe baseline

- patch: `docs/ops/upstream-migration/wave15-nd3b-gcu.patch`
- probe: `docs/ops/upstream-migration/wave15-nd3b-gcu-probe-2026-04-24.json`
- `git apply --check` result: pass (`exit_code=0`)

## Execution checklist

1. Apply patch:
   - `git apply docs/ops/upstream-migration/wave15-nd3b-gcu.patch`
2. Run bounded tests:
   - `uv run --package tools pytest tools/tests/test_browser_tools_comprehensive.py -q`
3. Run mandatory full gate:
   - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
4. Record execution artifact + update backlog focus.

## Execution result

- ND-3B patch replay executed successfully for all `7` scoped files;
- targeted test result:
  - `uv run --package tools pytest tools/tests/test_browser_tools_comprehensive.py -q`
  - `28 passed`;
- full regression gate result:
  - `ok=7 failed=0`;
- evidence artifact:
  - `docs/ops/upstream-migration/wave15-nd3b-execution-2026-04-24.json`.

## Rollback checklist

If gate fails before commit:

1. Restore only ND-3B files:
   - `git restore --worktree --staged -- tools/src/gcu/__init__.py`
   - `git restore --worktree --staged -- tools/src/gcu/browser/__init__.py`
   - `git restore --worktree --staged -- tools/src/gcu/browser/bridge.py`
   - `git restore --worktree --staged -- tools/src/gcu/browser/tools/inspection.py`
   - `git restore --worktree --staged -- tools/src/gcu/browser/tools/interactions.py`
   - `git restore --worktree --staged -- tools/src/gcu/browser/tools/tabs.py`
   - `git restore --worktree --staged -- tools/tests/test_browser_tools_comprehensive.py`
2. Re-run smoke gate:
   - `./scripts/upstream_sync_regression_gate.sh`

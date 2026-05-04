# Wave 15 — ND-2B Code-Bearing Replay Plan

Date: 2026-04-24
Status: executed (gate green)

## Scope

Code-bearing template files:

- `examples/templates/deep_research_agent/agent.py`
- `examples/templates/deep_research_agent/nodes/__init__.py`
- `examples/templates/meeting_scheduler/nodes/__init__.py`

## Probe evidence

- `docs/ops/upstream-migration/wave15-nd2b-code-probe-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd2b-code-bearing.patch`

Probe result:

- `git apply --check` passed (`exit_code=0`).

## Execution checklist

1. Confirm ND-2A state is stable and gated. (done)
2. Apply ND-2B patch:
   - `git apply docs/ops/upstream-migration/wave15-nd2b-code-bearing.patch` (done)
3. Run full regression gate:
   - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh` (done)
4. Verify changed scope:
   - `git diff --name-only -- examples/templates/deep_research_agent examples/templates/meeting_scheduler` (done)

## Execution result

- ND-2B patch applied successfully for scoped code-bearing files.
- Full regression gate result: `ok=7 failed=0`.
- Evidence artifact:
  - `docs/ops/upstream-migration/wave15-nd2b-execution-2026-04-24.json`.

## Rollback checklist

If gate fails before commit:

1. Restore only ND-2B files:
   - `git restore --worktree --staged -- examples/templates/deep_research_agent/agent.py`
   - `git restore --worktree --staged -- examples/templates/deep_research_agent/nodes/__init__.py`
   - `git restore --worktree --staged -- examples/templates/meeting_scheduler/nodes/__init__.py`
2. Re-run smoke gate:
   - `./scripts/upstream_sync_regression_gate.sh`

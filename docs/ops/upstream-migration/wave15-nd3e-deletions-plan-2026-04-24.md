# Wave 15 — ND-3E Deletions Policy Plan

Date: 2026-04-24
Status: executed

## Scope

Upstream-deleted legacy files:

- `tools/src/aden_tools/tools/google_auth.py`
- `tools/tests/tools/test_google_auth.py`

## Probe baseline

- `docs/ops/upstream-migration/wave15-nd3e-deletions-probe-2026-04-24.json`
- probe summary:
  - no external references found outside the two candidate files;
  - recommendation: `safe_to_delete`.

## Execution checklist

1. Remove both files from local tree.
2. Verify no references remain:
   - `rg -n "google_auth|get_google_access_token_from_env_or_file" tools/src tools/tests`
3. Run mandatory full gate:
   - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
4. Record execution artifact and update backlog/docs.

## Execution result

- both target files removed:
  - `tools/src/aden_tools/tools/google_auth.py`
  - `tools/tests/tools/test_google_auth.py`
- reference scan after deletion returned no matches.
- mandatory full gate passed: `ok=7 failed=0`.
- evidence:
  - `docs/ops/upstream-migration/wave15-nd3e-execution-2026-04-24.json`.

## Rollback checklist

If needed before commit:

1. Restore deleted files:
   - `git restore --worktree --staged -- tools/src/aden_tools/tools/google_auth.py`
   - `git restore --worktree --staged -- tools/tests/tools/test_google_auth.py`
2. Re-run smoke gate:
   - `./scripts/upstream_sync_regression_gate.sh`

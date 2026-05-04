# Wave 15 — ND-3D Runtime Packaging Replay Plan

Date: 2026-04-24
Status: executed (reconcile + gate green)

## Scope

Runtime packaging files (`4`):

- `tools/Dockerfile`
- `tools/coder_tools_server.py`
- `tools/mcp_servers.json`
- `tools/tests/test_coder_tools_server.py`

## Probe baseline

- patch: `docs/ops/upstream-migration/wave15-nd3d-runtime.patch`
- probe: `docs/ops/upstream-migration/wave15-nd3d-runtime-probe-2026-04-24.json`
- reconcile table: `docs/ops/upstream-migration/wave15-nd3d-runtime-reconcile-2026-04-24.json`
- `git apply --check` result: fail (`exit_code=1`)
  - failing hunk: `tools/coder_tools_server.py` (local divergence).

## Execution protocol (reconcile mode)

1. Reconcile `tools/coder_tools_server.py` manually (`ours` + upstream delta).
2. Replay remaining ND-3D files from upstream where safe.
3. Validate bounded scope:
   - `uv run --package tools pytest tools/tests/test_coder_tools_server.py -q`
4. Run mandatory full gate:
   - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`

## Execution result

- reconcile execution completed for ND-3D scope (`4` files);
- `coder_tools_server.py` reconciled with upstream concepts while keeping local extensions:
  - loader/runner MCP import fallback;
  - write-root aware write resolver and `--write-root` CLI;
  - `register_file_tools(... resolve_path_write=..., project_root=WRITE_ROOT)`.
- local-only decisions preserved intentionally:
  - `tools/Dockerfile` (`uv` + workspace-based install strategy);
  - `tools/mcp_servers.json` (multi-server topology);
  - extended `tools/tests/test_coder_tools_server.py` coverage.
- validation:
  - targeted tests:
    - `uv run --package tools pytest tools/tests/test_coder_tools_server.py -q` -> `7 passed`;
  - full regression gate:
    - `ok=7 failed=0`.
- execution evidence:
  - `docs/ops/upstream-migration/wave15-nd3d-execution-2026-04-24.json`.

## Rollback checklist

If gate fails before commit:

1. Restore only ND-3D files:
   - `git restore --worktree --staged -- tools/Dockerfile`
   - `git restore --worktree --staged -- tools/coder_tools_server.py`
   - `git restore --worktree --staged -- tools/mcp_servers.json`
   - `git restore --worktree --staged -- tools/tests/test_coder_tools_server.py`
2. Re-run smoke gate:
   - `./scripts/upstream_sync_regression_gate.sh`

# Wave 15 — ND-3A Prometheus Replay Plan

Date: 2026-04-24
Status: executed (gate green)

## Scope

Bounded files (`8`):

- `tools/src/aden_tools/credentials/health_check.py`
- `tools/src/aden_tools/credentials/prometheus.py`
- `tools/src/aden_tools/tools/__init__.py`
- `tools/src/aden_tools/tools/prometheus_tool/README.md`
- `tools/src/aden_tools/tools/prometheus_tool/__init__.py`
- `tools/src/aden_tools/tools/prometheus_tool/prometheus_tool.py`
- `tools/tests/test_health_checks.py`
- `tools/tests/tools/test_prometheus_tool.py`

## Probe baseline

- patch: `docs/ops/upstream-migration/wave15-nd3a-prometheus.patch`
- probe: `docs/ops/upstream-migration/wave15-nd3a-prometheus-probe-2026-04-24.json`
- reconcile table: `docs/ops/upstream-migration/wave15-nd3a-prometheus-reconcile-2026-04-24.json`
- `git apply --check` result: fail (`exit_code=1`)

## Execution protocol (reconcile mode)

1. Build per-file reconcile table (`ours/upstream` sha + conflict class).
2. For divergent files, apply targeted semantic merges (not blind patch):
   - `health_check.py`
   - `tools/__init__.py`
   - `test_health_checks.py`
3. Add upstream-missing files:
   - `tools/src/aden_tools/tools/prometheus_tool/README.md`
   - `tools/tests/tools/test_prometheus_tool.py`
4. Validate bounded lane:
   - `uv run --package tools pytest tools/tests/test_health_checks.py -q`
   - `uv run --package tools pytest tools/tests/tools/test_prometheus_tool.py -q`
5. Run mandatory full gate:
   - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`

## Execution result

- reconcile execution completed for bounded scope (`8` files);
- added upstream-missing files:
  - `tools/src/aden_tools/tools/prometheus_tool/README.md`;
  - `tools/tests/tools/test_prometheus_tool.py`;
- aligned `prometheus.py` and `prometheus_tool.py` to upstream content;
- preserved intentional local divergence in:
  - `tools/src/aden_tools/credentials/health_check.py`;
  - `tools/src/aden_tools/tools/__init__.py`;
- validation:
  - targeted tests: `48 passed`;
  - full regression gate: `ok=7 failed=0`.
- execution evidence:
  - `docs/ops/upstream-migration/wave15-nd3a-execution-2026-04-24.json`.

## Rollback protocol (pre-commit only)

1. Restore bounded files:
   - `git restore --worktree --staged -- tools/src/aden_tools/credentials/health_check.py`
   - `git restore --worktree --staged -- tools/src/aden_tools/credentials/prometheus.py`
   - `git restore --worktree --staged -- tools/src/aden_tools/tools/__init__.py`
   - `git restore --worktree --staged -- tools/src/aden_tools/tools/prometheus_tool/README.md`
   - `git restore --worktree --staged -- tools/src/aden_tools/tools/prometheus_tool/__init__.py`
   - `git restore --worktree --staged -- tools/src/aden_tools/tools/prometheus_tool/prometheus_tool.py`
   - `git restore --worktree --staged -- tools/tests/test_health_checks.py`
   - `git restore --worktree --staged -- tools/tests/tools/test_prometheus_tool.py`
2. Re-run smoke gate:
   - `./scripts/upstream_sync_regression_gate.sh`

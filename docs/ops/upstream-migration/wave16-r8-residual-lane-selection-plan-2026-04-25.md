# Wave16-R8 Residual Lane Selection Plan (2026-04-25)

## Preconditions

- Wave16-R6 completed:
  - `docs/ops/upstream-migration/wave16-r6-runtime-warning-noise-hardening-execution-2026-04-25.json`
- Wave16-R7 completed:
  - `docs/ops/upstream-migration/wave16-r7-autonomous-ops-status-flake-stabilization-execution-2026-04-25.json`
- full regression gate soak after R7:
  - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
  - result: `ok=7 failed=0` (consecutive post-fix runs)

## Residual Shortlist (post-soak)

Lightweight `upstream/main` numstat probe (core/framework focus):

- `core/framework/loader/mcp_client.py` → `+5 / -1`
- `core/framework/loader/mcp_registry.py` → `+2 / -2`
- `core/framework/server/routes_config.py` → `+3 / -2`
- `core/framework/server/routes_logs.py` → `+12 / -6`
- `core/framework/server/routes_credentials.py` → `+321 / -268` (deferred; high blast radius)
- `core/framework/server/routes_execution.py` → `+150 / -23` (deferred; high blast radius)
- `core/framework/server/routes_queens.py` → `+95 / -51` (deferred; medium/high blast radius)

## Selection

Selected next bounded lane: **R8A = `core/framework/loader/mcp_client.py`**

Why:

- smallest non-trivial delta (`+5/-1`);
- isolated to MCP session cleanup path;
- aligns with already completed runtime-noise hardening objective;
- minimal API surface and low regression blast radius.

## Candidate Change Contract (R8A)

Observed local delta vs upstream:

- in `_cleanup_stdio_async()` local branch classifies known anyio cancel-scope cross-task teardown quirk and logs it at debug level;
- non-quirk cleanup failures remain warning-level.

Execution intent:

- keep behavior unless upstream now provides an equivalent fix;
- if upstream changed this area, reconcile by preserving local quirk classification and upstream-compatible flow;
- avoid broader loader/mcp registry behavior changes in this lane.

## Validation Matrix (R8A)

Mandatory:

1. `uv run --package framework pytest core/framework/server/tests/test_api.py -k "mcp or credentials or health" -q`
2. `uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q`
3. `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
   - expected: `ok=7 failed=0`

Optional spot-check:

1. run a local MCP teardown smoke to confirm no warning spam for known cancel-scope quirk in shutdown path.

## Guardrails

- No destructive lane apply.
- Preserve AppKey/container-first local contracts.
- If any contract drift appears outside `mcp_client.py`, reclassify lane as `reconcile_only` and defer.

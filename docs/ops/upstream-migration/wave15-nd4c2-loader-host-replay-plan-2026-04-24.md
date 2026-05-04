# Wave 15 — ND-4C2 Loader/Host Replay Plan

Date: 2026-04-24
Status: ready for bounded execution

## Scope

- `core/framework/loader/agent_loader.py`
- `core/framework/loader/mcp_client.py`
- `core/framework/loader/tool_registry.py`
- `core/framework/host/agent_host.py`
- `core/framework/host/colony_metadata.py`
- `core/framework/host/colony_runtime.py`
- `core/framework/host/colony_tools_config.py`
- `core/framework/host/event_bus.py`

Patch artifact:

- `docs/ops/upstream-migration/wave15-nd4c2-loader-host.patch`

Probe artifact:

- `docs/ops/upstream-migration/wave15-nd4c2-loader-host-probe-2026-04-24.json`

Probe summary:

- `git apply --check` passed (`exit_code=0`).

## Execution checklist

1. Apply bounded patch:
   - `git apply docs/ops/upstream-migration/wave15-nd4c2-loader-host.patch`
2. Run targeted checks (loader/host paths + related tests).
3. Run mandatory full regression gate:
   - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
4. Record ND-4C2 execution artifact and update backlog/docs.

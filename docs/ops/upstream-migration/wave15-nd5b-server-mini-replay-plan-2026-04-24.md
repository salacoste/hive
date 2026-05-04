# Wave 15 ND-5B Replay Plan (Server mini-lane)

Date: 2026-04-24

Scope:
- `core/framework/server/README.md`
- `core/framework/server/routes_events.py`

Patch/probe artifacts:
- `docs/ops/upstream-migration/wave15-nd5b-server-mini.patch`
- `docs/ops/upstream-migration/wave15-nd5b-server-mini-probe-2026-04-24.json`

## Probe result

`git apply --check` is not clean for both scoped files, so this lane requires manual reconcile.

## Reconcile strategy

1. `README.md`
- Align `SessionManager` access examples with AppKey constants (`APP_KEY_MANAGER`) where local runtime already migrated to typed AppKeys.
- Keep local behavior docs for Telegram/Web bridge/container-first flow intact.

2. `routes_events.py`
- Compare upstream trigger event set with local runtime expectations.
- Decide explicitly whether `EventType.TRIGGER_FIRED` remains part of SSE payload contract.
- If retained locally, document divergence in lane execution artifact.

## Validation plan

1. Targeted server checks:
- `uv run --package framework pytest core/framework/server/tests/test_api.py -k "events or health" -q`

2. Full regression gate:
- `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`

## Exit criteria

- Reconcile decision recorded for trigger event contract.
- Targeted checks green.
- Full gate green.
- Execution artifact added and backlog focus moved to next lane.

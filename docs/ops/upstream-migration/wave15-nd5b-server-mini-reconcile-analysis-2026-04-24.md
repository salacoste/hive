# ND-5B Reconcile Analysis (Server mini-lane)

Date: 2026-04-24

Scope:
- `core/framework/server/README.md`
- `core/framework/server/routes_events.py`

## Findings

1. `README.md`
- Upstream text shows legacy access pattern: `request.app["manager"]`.
- Local runtime already migrated to AppKey constants and typed access (`APP_KEY_MANAGER`) to avoid aiohttp AppKey warnings and keep server docs consistent with current codebase conventions.
- Decision: keep local text; treat upstream line as non-adoptable for current runtime contract.

2. `routes_events.py`
- Upstream removes `EventType.TRIGGER_FIRED` from event types exposed by `/api/events` filtered stream.
- Local runtime publishes and consumes `TRIGGER_FIRED` in multiple places:
  - `core/framework/tools/queen_lifecycle_tools.py` emits it;
  - Event type exists in both runtime/host event buses;
  - server/session flow references trigger lifecycle around this event family.
- Decision: keep local inclusion of `TRIGGER_FIRED` unless a broader trigger-contract migration is planned end-to-end.

## Interim outcome

- ND-5B patch is intentionally non-clean for current local contracts.
- Lane remains in reconcile/planning mode; apply is deferred until a dedicated trigger-stream contract decision is approved.

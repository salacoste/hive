# Wave16-R1 Residual Governance Plan (2026-04-25)

## Inputs

- `docs/ops/upstream-migration/wave15-post-nd5f-residual-inventory-2026-04-25.json`
- `docs/ops/upstream-migration/wave15-post-nd5f-residual-triage-2026-04-25.md`

## Goal

Before any new upstream replay:
- lock intentional local divergences into an explicit allowlist;
- isolate one minimal-risk replay candidate outside allowlist;
- keep full gate baseline green.

## Draft keep-local allowlist (core/framework)

Operationally protected (do not replay from upstream blindly):
- `core/framework/config.py`
- `core/framework/host/event_bus.py`
- `core/framework/loader/cli.py`
- `core/framework/loader/mcp_client.py`
- `core/framework/loader/mcp_registry.py`
- `core/framework/server/routes_config.py`
- `core/framework/server/routes_messages.py`
- `core/framework/server/routes_logs.py`
- `core/framework/agents/queen/mcp_registry.json`

High-risk deferred lanes (require dedicated bounded wave, not R1):
- `core/framework/server/session_manager.py`
- `core/framework/server/routes_sessions.py`
- `core/framework/server/queen_orchestrator.py`
- `core/framework/server/routes_credentials.py`
- `core/framework/server/tests/test_api.py`
- `core/framework/llm/litellm.py`

## Candidate shortlist (outside allowlist)

1. `core/framework/server/README.md`
- diff size: `1/1`
- runtime impact: none
- risk: low

2. `core/framework/server/tests/test_queen_orchestrator.py`
- diff size: `52/56`
- runtime impact: test-only
- risk: medium

3. `core/framework/agent_loop/internals/cursor_persistence.py`
- diff size: `5/15`
- runtime impact: runtime behavior
- risk: medium

## Selected next bounded candidate

- `Wave16-R2`: `core/framework/server/README.md`
- Rationale: smallest delta and no runtime blast radius; validates replay governance flow before moving to runtime files.

## R2 execution outcome (reconcile)

- result: `keep_local` (no replay apply)
- rationale:
  - runtime code uses `request.app[APP_KEY_MANAGER]` consistently;
  - upstream README line still references legacy `request.app["manager"]` text.
- execution artifact:
  - `docs/ops/upstream-migration/wave16-r2-server-readme-reconcile-execution-2026-04-25.json`
- handoff:
  - proceed to `Wave16-R3` bounded candidate planning in `core/framework/server/tests`.

## R3 triage outcome (server/orchestrator tests)

- triage artifact:
  - `docs/ops/upstream-migration/wave16-r3-server-orchestrator-test-contract-triage-2026-04-25.md`
- decision:
  - `reconcile_only` (do not replay upstream test file verbatim);
  - upstream contract is legacy vs current `create_queen(...)` signature.
- blocker observed during runtime probe:
  - direct `create_queen(...)` probe currently fails with
    `ImportError: cannot import name '_QUEEN_BUILDING_TOOLS' from framework.agents.queen.nodes`.
- next lane:
  - `Wave16-R4` import-contract reconcile for queen orchestrator runtime path.
  - initial map artifact:
    - `docs/ops/upstream-migration/wave16-r4-queen-import-contract-map-2026-04-25.json`
    - `required_symbols=29`, `missing_symbols=25`.

## Exit criteria for R1

- allowlist committed in migration docs/backlog;
- R2 candidate selected and referenced from backlog Current Focus;
- full regression gate remains green.

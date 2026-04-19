# Replay Validation Plan (Wave 3)

Date: 2026-04-18

## Scope

Validation checklist after replaying Wave 3 control-plane bundle onto landing branch.

## Preconditions

1. Landing branch checked out from `origin/main`.
2. Replay bundle applied.
3. Docker runtime available.

## Validation Sequence

1. Baseline preflight:

```bash
./scripts/upstream_sync_preflight.sh origin/main
```

2. API and bridge contract tests:

```bash
./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -q
./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q
```

3. Container-first ops checks:

```bash
docker compose up -d --build hive-core hive-scheduler
./scripts/local_prod_checklist.sh
HIVE_AUTONOMOUS_HEALTH_PROFILE=prod ./scripts/autonomous_ops_health_check.sh
```

4. Autonomous delivery smoke:

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py
```

5. MCP access baseline:

```bash
./scripts/verify_access_stack.sh
./scripts/hive_ops_run.sh uv run --no-project python scripts/mcp_health_summary.py --since-minutes 30
```

## Exit Criteria

1. API + Telegram tests pass.
2. Local prod checklist passes.
3. Autonomous health gate passes.
4. Delivery smoke passes.
5. MCP health summary is `ok`.

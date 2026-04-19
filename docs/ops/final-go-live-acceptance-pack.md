# Final Go-Live Acceptance Pack (Local)

Date: `2026-04-10`

## Objective

Confirm that Hive local production setup is operational for autonomous multi-project development with deterministic governance and explicit remediation paths.

## Acceptance Matrix

1. Runtime core
   - `curl -fsS http://localhost:${HIVE_CORE_PORT:-8787}/api/health` -> `status=ok`.
2. Autonomous pipeline determinism
   - `uv run pytest core/framework/server/tests/test_api.py -k "pipeline_" -q` -> `27 passed`.
   - Deterministic subset (`retry/escalation/report/terminal`) -> `5 passed`.
3. MCP required stack
   - `uv run python scripts/mcp_health_summary.py --since-minutes 30` -> `status=ok`, `5/5`.
4. Ops recovery readiness
   - stale remediation apply executed (`selected_total=223`, `remediated_total=223`);
   - post-check `./scripts/autonomous_ops_health_check.sh` -> `stuck_runs=0`, `no_progress_projects=0`;
   - `./scripts/autonomous_ops_drill.sh` -> `ok=5 failed=0`.
5. Governance and guardrails
   - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=20 failed=0`;
   - backlog validation + status drift -> `ok`, `in_progress=[]`, `done=107`.

## Operator Notes

1. Container-only scheduler baseline is enabled via `hive-scheduler` service in `docker compose`.
2. Host schedulers (`launchd/cron`) are optional legacy fallback and can remain disabled.
3. Cross-machine rollout uses only Docker services (`hive-core`, `hive-scheduler`, `redis`, `postgres`, token refresher).

## Decision

System is ready for controlled local operation and cross-machine rollout in container-only mode with full guardrail coverage.

# Overlap Batch A Landing Rehearsal Snapshot

- Generated: 2026-04-18T01:14:59Z
- Target ref: origin/main
- Target SHA: 3c2161aad540610ae88c2c2d4b20ced82ca2d35d
- Landing branch: migration/upstream-wave3
- Replay bundle: `docs/ops/upstream-migration/replay-bundles/wave3-20260417-213932.tar.gz`
- Dependency bundle: `docs/ops/upstream-migration/replay-bundles/wave3-batch-a-dependency-20260418-011208.tar.gz`
- Hotspots bundle: `docs/ops/upstream-migration/replay-bundles/wave3-batch-a-hotspots-20260418-011209.tar.gz`
- Changed paths after apply: `51`

## Gate Results

- `test_api.py`: `ok`
- `test_telegram_bridge.py`: `ok`
- `test_queen_orchestrator.py`: `ok`

## Working Tree Snapshot

```
 M core/framework/server/app.py
 M core/framework/server/queen_orchestrator.py
 M core/framework/server/routes_credentials.py
 M core/framework/server/routes_execution.py
 M core/framework/server/routes_sessions.py
 M core/framework/server/session_manager.py
 M core/framework/server/tests/test_api.py
 M core/framework/server/tests/test_queen_orchestrator.py
?? core/framework/graph/
?? core/framework/llm/fallback.py
?? core/framework/model_routing.py
?? core/framework/runner/
?? core/framework/runtime/
?? core/framework/server/autonomous_pipeline.py
?? core/framework/server/project_execution.py
?? core/framework/server/project_metrics.py
?? core/framework/server/project_onboarding.py
?? core/framework/server/project_policy.py
?? core/framework/server/project_retention.py
?? core/framework/server/project_store.py
?? core/framework/server/project_templates.py
?? core/framework/server/project_toolchain.py
?? core/framework/server/routes_autonomous.py
?? core/framework/server/routes_graphs.py
?? core/framework/server/routes_projects.py
?? core/framework/server/telegram_bridge.py
?? core/framework/server/tests/test_telegram_bridge.py
?? core/frontend/src/api/autonomous.ts
?? core/frontend/src/api/projects.ts
?? docs/LOCAL_PROD_RUNBOOK.md
?? docs/autonomous-factory/
?? scripts/acceptance_gate_presets.sh
?? scripts/acceptance_gate_presets_smoke.sh
?? scripts/acceptance_ops_summary.py
?? scripts/acceptance_report_artifact.py
?? scripts/acceptance_report_digest.py
?? scripts/acceptance_report_hygiene.py
?? scripts/acceptance_report_regression_guard.py
?? scripts/acceptance_scheduler_snapshot.sh
?? scripts/acceptance_toolchain_self_check.sh
?? scripts/acceptance_toolchain_self_check_deep.sh
?? scripts/acceptance_weekly_maintenance.sh
?? scripts/autonomous_acceptance_gate.sh
?? scripts/autonomous_delivery_e2e_smoke.py
?? scripts/autonomous_loop_tick.sh
?? scripts/autonomous_operator_profile.sh
?? scripts/autonomous_ops_drill.sh
?? scripts/autonomous_ops_health_check.sh
?? scripts/autonomous_remediate_stale_runs.sh
?? scripts/autonomous_scheduler_daemon.py
?? scripts/verify_access_stack.sh
```

# 21. Upstream Migration Wave 3 Plan (`origin/main` -> local factory)

Date: 2026-04-17

## Goal

Safely migrate to latest upstream (`origin/main`) while preserving local autonomous factory behavior:

1. project-scoped execution model,
2. autonomous pipeline + ops controls,
3. Telegram control center,
4. container-first runtime and runbooks.

## Baseline (verified)

Snapshot source: `docs/ops/upstream-migration/baseline-2026-04-17.md`.

- branch delta: `0 ahead / 225 behind` (`main...origin/main`);
- upstream file delta entries: `649`;
- upstream change profile:
  - `M=419`, `A=106`, `D=79`, `R=45`;
- local workspace changed paths: `213`;
- overlap `local_changed ∩ upstream_changed`: `68` (direct conflict zone);
- local-only changed paths (must be preserved by design): `145`.

Key observation:

- upstream includes major architecture movement (`graph/runtime/runner` -> `orchestrator/host/loader`);
- unclassified decision registry coverage for current wave is now complete (`other_unclassified=634`, `missing=0`, `stale=0`, refreshed April 18, 2026).

## Non-Negotiable Guardrails

1. Do not regress project isolation (`project_id` boundaries).
2. Do not regress autonomous APIs (`/api/projects/*/autonomous/*`, loop/remediation/status).
3. Do not regress Telegram bridge behavior and operator controls.
4. Do not regress container-first operational scripts and runbooks.
5. No direct blind merge of `origin/main` into current dirty workspace.

## Migration Strategy (recommended)

Use **forward-port strategy** (upstream-first, then controlled local replay), not in-place merge on current dirty tree.

### Phase 0 - Freeze and Evidence

1. Freeze current local baseline and artifacts:
   - `./scripts/local_prod_checklist.sh`
   - `./scripts/acceptance_toolchain_self_check.sh`
   - `HIVE_AUTONOMOUS_HEALTH_PROFILE=prod ./scripts/autonomous_ops_health_check.sh`
2. Create state backups:
   - `./scripts/backup_hive_state.sh`
3. Capture migration baseline:
   - `./scripts/hive_ops_run.sh uv run --no-project python scripts/upstream_delta_status.py --json`
   - `git rev-list --left-right --count main...origin/main`
   - `git diff --name-status main..origin/main`

Exit criteria:

- all three operational gates pass;
- baseline artifacts are committed to docs.

### Phase 1 - Upstream Landing Branch

1. Create a dedicated migration branch from `origin/main` (clean tree).
2. Bring only local factory domains as replay bundles:
   - `core/framework/server/project_*`
   - `core/framework/server/routes_projects.py`
   - `core/framework/server/routes_autonomous.py`
   - `core/framework/server/telegram_bridge.py`
   - `core/framework/server/autonomous_pipeline.py`
   - `core/frontend/src/api/{projects,autonomous}.ts`
   - factory runbooks and ops scripts under `scripts/` and `docs/`.

Exit criteria:

- project/autonomous/telegram core compiles and boots in docker.

### Phase 2 - Conflict Resolution by Batches

Resolve overlap set (`68` files) in bounded batches:

1. Server control-plane batch (`core/framework/server/*`, tests).
2. Frontend operator UX batch (`core/frontend/*` overlap subset).
3. Tools/MCP compatibility batch (`tools/src/*`, `tools/tests/*` overlap subset).
4. Templates/docs batch (low-risk).

Rules:

- one batch at a time;
- no mixed high-risk architecture shifts and low-risk docs in one commit.

Exit criteria:

- each batch has explicit test evidence and rollback note.

### Phase 3 - Unclassified Delta Governance Refresh

1. Rebuild decision registry coverage for current wave:
   - refresh decisions for the 634 unclassified paths;
   - close missing decision gap (`619` currently).
2. Update:
   - `docs/ops/upstream-unclassified-decisions.json`
   - `docs/ops/upstream-unclassified-decisions.md`
3. Re-run:
   - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_unclassified_delta_decisions.py`

Exit criteria:

- checker passes with no missing decisions.

Status update (April 18, 2026):

- completed;
- `scripts/check_unclassified_delta_decisions.py` passes with `covered_unclassified=634`, `stale_decisions=0`;
- report sync check passes:
  - `scripts/render_unclassified_decision_report.py --check docs/ops/upstream-unclassified-decisions.md`.

### Phase 4 - Regression and Operational Gate

Required validation on migration branch:

1. `./scripts/acceptance_toolchain_self_check.sh`
2. `./scripts/check_runtime_parity.sh`
3. `./scripts/local_prod_checklist.sh`
4. `./scripts/hive_ops_run.sh uv run --no-project python scripts/mcp_health_summary.py --since-minutes 30`
5. `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -q`
6. `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q`
7. `./scripts/hive_ops_run.sh uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py`

Exit criteria:

- all gates pass in container-first mode.

### Phase 5 - Cutover

1. Merge migration branch.
2. Rebuild runtime:
   - `docker compose up -d --build hive-core hive-scheduler`
3. Post-merge smoke:
   - `/api/health`
   - Telegram smoke (`/status`, `/sessions`, plain text, one bootstrap flow).

Exit criteria:

- operator flow works end-to-end without manual hotfixes.

## Conflict Hotspots (priority)

1. `core/framework/server/app.py`, `routes_execution.py`, `routes_sessions.py`, `session_manager.py`
2. `core/framework/server/queen_orchestrator.py`
3. `core/framework/server/routes_credentials.py`
4. `core/frontend/src/pages/workspace.tsx`, `my-agents.tsx`, `HistorySidebar.tsx`
5. `tools/src/aden_tools/tools/github_tool/github_tool.py`
6. `tools/src/aden_tools/tools/{gmail_tool,google_docs_tool,google_sheets_tool}.py`
7. `core/framework/llm/litellm.py`, `core/framework/agents/queen/*memory*`

## Local Factory Modules to Preserve (must survive migration)

1. `core/framework/server/routes_projects.py`
2. `core/framework/server/routes_autonomous.py`
3. `core/framework/server/project_onboarding.py`
4. `core/framework/server/project_toolchain.py`
5. `core/framework/server/project_policy.py`
6. `core/framework/server/project_execution.py`
7. `core/framework/server/project_retention.py`
8. `core/framework/server/telegram_bridge.py`
9. `core/framework/server/autonomous_pipeline.py`
10. `scripts/autonomous_*`, `scripts/acceptance_*`, `scripts/verify_access_stack.sh`
11. `docs/LOCAL_PROD_RUNBOOK.md` and `docs/autonomous-factory/*`

## Rollback Strategy

If any migration batch fails:

1. revert only the failing batch commit(s);
2. rerun:
   - `./scripts/check_runtime_parity.sh`
   - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -q`
   - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q`
3. mark batch as blocked with reason and remediation hypothesis.

## Definition of Done for this migration

1. Upstream target merged (latest `origin/main` at migration start).
2. Local factory modules preserved and operational.
3. Container-first gates are green.
4. Telegram + autonomous ops smoke passed.
5. Updated decision registry and evidence docs committed.

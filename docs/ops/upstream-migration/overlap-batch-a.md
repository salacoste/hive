# Overlap Batch A (Server Hotspots)

Date: 2026-04-18

## Scope

Server hotspot integration for upstream landing:

1. `core/framework/server/app.py`
2. `core/framework/server/session_manager.py`
3. `core/framework/server/routes_execution.py`
4. `core/framework/server/routes_sessions.py`
5. `core/framework/server/queen_orchestrator.py`
6. `core/framework/server/routes_credentials.py`

## Artifacts

1. Full export:
   - `docs/ops/upstream-migration/overlap-batch-a-latest.patch`
   - `docs/ops/upstream-migration/overlap-batch-a-latest.md`
2. Focus map:
   - `docs/ops/upstream-migration/overlap-batch-a-focus-latest.md`
3. Focus patch:
   - `docs/ops/upstream-migration/overlap-batch-a-focus-latest.patch`
   - `docs/ops/upstream-migration/overlap-batch-a-focus-summary-latest.md`
4. Probe reports:
   - `docs/ops/upstream-migration/overlap-batch-a-focus-probe-latest.md`
   - `docs/ops/upstream-migration/overlap-batch-a-conflict-probe-latest.md`
   - `docs/ops/upstream-migration/overlap-batch-a-integration-probe-latest.md`
5. Dependency bundle:
   - `docs/ops/upstream-migration/overlap-batch-a-dependency-bundle-latest.md`
6. Hotspots bundle:
   - `docs/ops/upstream-migration/overlap-batch-a-hotspots-bundle-latest.md`
7. Landing rehearsal:
   - `docs/ops/upstream-migration/overlap-batch-a-landing-rehearsal-latest.md`
8. Landing integration:
   - `docs/ops/upstream-migration/overlap-batch-a-landing-integration-latest.md`

## Scripts

1. `scripts/upstream_overlap_batch_a_export.sh`
2. `scripts/upstream_overlap_batch_a_focus_map.sh`
3. `scripts/upstream_overlap_batch_a_focus_patch.py`
4. `scripts/upstream_overlap_batch_a_focus_probe.sh`
5. `scripts/upstream_overlap_batch_a_conflict_probe.sh`
6. `scripts/upstream_overlap_batch_a_file_probe.sh`
7. `scripts/upstream_overlap_batch_a_apply.sh`
8. `scripts/upstream_overlap_batch_a_integration_probe.sh`
9. `scripts/upstream_overlap_batch_a_dependency_bundle.sh`
10. `scripts/upstream_overlap_batch_a_hotspots_bundle.sh`
11. `scripts/upstream_overlap_batch_a_landing_rehearsal.sh`
12. `scripts/upstream_overlap_batch_a_bundle_apply.sh`
13. `scripts/upstream_overlap_batch_a_landing_integrate.sh`

## Current Finding

1. Focus patch remains useful for conflict mapping and activation audit:
   - `git apply --check` and `git apply --3way --index` are clean for focused hunks.
2. Integration probe evidence (`overlap-batch-a-integration-probe-latest.md`):
   - baseline (`replay + focus patch`, no overlays) fails with
     `ModuleNotFoundError: No module named 'framework.runtime'`;
   - mergeable compatibility fix landed in local tree:
     - `core/framework/runner/__init__.py` switched to lazy exports for
       `AgentRunner/AgentInfo/ValidationResult` to prevent import cycle during package init;
   - with this fix, overlay (`runtime + graph + runner + routes_graphs.py`) is green:
     - app smoke: `ok`;
     - `pytest core/framework/server/tests/test_api.py -k "health" -q`: `ok`.
3. Deterministic apply path for Batch A now uses bundles (instead of hunk-only patch apply):
   - dependency bundle: runtime/graph/runner/model-routing/fallback/routes_graphs;
   - hotspots bundle: six server hotspot files.
4. Landing rehearsal on clean `origin/main` clone is green with local backend contracts:
   - `test_api.py` profile subset (session/execution/credentials + health): `ok`;
   - `test_telegram_bridge.py`: `ok`;
   - `test_queen_orchestrator.py`: `ok`.
5. Landing integration evidence is recorded:
   - clean landing clone commit:
     - `ff9b88b9a51071d4c5c3b2d82346c2bfb807080a`;
   - gate results:
     - `test_api` profile subset = `ok`;
     - `test_telegram_bridge.py` = `ok`;
     - `test_queen_orchestrator.py` = `ok`;
     - `test_control_plane_contract` = `ok`.

## Apply Step (landing branch only)

Preferred deterministic path (bundle-based):

```bash
HIVE_UPSTREAM_LANDING_BRANCH=migration/upstream-wave3 \
./scripts/upstream_overlap_batch_a_bundle_apply.sh --check

HIVE_UPSTREAM_LANDING_BRANCH=migration/upstream-wave3 \
./scripts/upstream_overlap_batch_a_bundle_apply.sh --apply
```

Legacy hunk-based path (kept for conflict diagnostics):

```bash
HIVE_UPSTREAM_LANDING_BRANCH=migration/upstream-wave3 \
./scripts/upstream_overlap_batch_a_apply.sh --check

HIVE_UPSTREAM_LANDING_BRANCH=migration/upstream-wave3 \
./scripts/upstream_overlap_batch_a_apply.sh --apply
```

Guardrails:

1. script exits if current branch is not `migration/upstream-wave3`;
2. script exits on dirty worktree unless `HIVE_UPSTREAM_ALLOW_DIRTY=true`.

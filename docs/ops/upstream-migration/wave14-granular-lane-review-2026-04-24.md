# Wave 14 — Granular Deferred-Lane Review Table

Date: 2026-04-24
Status: closure-ready (lane decisions finalized)

## Source snapshot

Derived from destructive delta on `HEAD..upstream/main` for:

- `.github/workflows/**`
- `scripts/**`

Probe command:

```bash
uv run --no-project python - <<'PY'
import subprocess
print(subprocess.check_output(
    ['git', 'diff', '--name-status', 'HEAD..upstream/main'],
    text=True,
))
PY
```

Current size:

- `.github/workflows/**`: `3` deletes
- `scripts/**`: `164` deletes (`126` root scripts + `38` tests)

## Workflow file-level decisions

| Path | Decision | Rationale | Replacement / Migration |
| --- | --- | --- | --- |
| `.github/workflows/docker-compose-smoke.yml` | `keep-local` | Required CI smoke for container startup and API baseline in this fork. | Keep workflow; re-evaluate only after equivalent gate exists and passes. |
| `.github/workflows/secret-scan.yml` | `keep-local` | Repository-level secret scan is a mandatory security control. | Keep workflow; no replacement needed. |
| `.github/workflows/upstream-sync-watch.yml` | `keep-local` | Needed for scheduled upstream drift visibility in fork governance model. | Keep workflow; no replacement needed. |

## Scripts lane grouped decisions (initial)

| Path pattern | Count | Decision | Rationale | Replacement / Migration |
| --- | ---: | --- | --- | --- |
| `scripts/tests/**` | 38 | `keep-local` | Regression coverage for local ops/acceptance guardrails. | Keep tests while scripts are retained. |
| `scripts/upstream_*` | 32 | `keep-local-provisional` | Upstream sync toolchain is fork-specific and currently active. | Per-file table completed (round 2); keep while replay workflow is active. |
| `scripts/install_*`, `scripts/status_*`, `scripts/uninstall_*` | 27 | `keep-local-provisional` | Scheduler/runtime operators for container and host modes. | Per-file table completed (round 10); keep until scheduler policy migration is finalized. |
| `scripts/check_*` | 17 | `keep-local-provisional` | Contract/sanity checks protect autonomous factory invariants. | Per-file table completed (round 3); keep until equivalent checks exist and pass. |
| `scripts/acceptance_*` | 11 | `keep-local-provisional` | Acceptance and reporting flow used in release gates. | Per-file table completed (round 4); keep until acceptance pipeline replacement is proven. |
| `scripts/autonomous_*` | 8 | `keep-local-provisional` | Autonomous loop operation and health automation. | Per-file table completed (round 5); keep until autonomous operator replacement is accepted. |
| `scripts/backlog_*` | 5 | `keep-local-provisional` | Backlog artifacts and hygiene contracts. | Per-file table completed (round 6); keep until backlog contract migration is complete. |
| `scripts/google_*` | 5 | `keep-local-provisional` | OAuth refresh/canary operations for Google MCPs. | Per-file table completed (round 7); keep until rotation runbook and canary parity are replaced. |
| `scripts/hive_*` | 4 | `keep-local-provisional` | Container-first operational wrappers. | Per-file table completed (round 8); keep until compatible ops wrappers are available. |
| `scripts/verify_*` | 1 | `keep-local-provisional` | Access-stack validation used in production checklist. | Per-file table completed (round 9); keep until equivalent validation is adopted. |
| `scripts/(root misc)` | 16 | `keep-local` | Mixed operational bootstrap/backup/tooling scripts. | Per-file table completed (round 1). |

## `scripts/(root misc)` per-file table (round 1)

Reference signal uses in-repo `rg` hits (operational hint only).

| Path | Ref hits | Decision | Rationale | Replacement / Migration |
| --- | ---: | --- | --- | --- |
| `scripts/_cron_job_lib.sh` | 16 | `keep-local` | Shared scheduler helper used by install/status/uninstall scripts. | Keep until scheduler lane is migrated together. |
| `scripts/apply_hive_toolchain_profile.sh` | 10 | `keep-local` | Used by toolchain planning/approval flow. | Keep until replacement profile flow is accepted. |
| `scripts/audit_mcp_credentials.py` | 17 | `keep-local` | Runbook baseline command for MCP credential readiness. | Keep; no replacement currently. |
| `scripts/backup_hive_state.sh` | 7 | `keep-local` | Backup operation is part of local-prod safety path. | Keep until backup/restore lane is redesigned. |
| `scripts/bootstrap_autonomous_factory.sh` | 0 | `keep-local` | Bootstrap helper for autonomous-factory templates; ties directly to `validate_factory_config.sh`. | Keep until template/bootstrap flow is replaced end-to-end. |
| `scripts/detect_project_toolchains.py` | 6 | `keep-local` | Used by toolchain profile detection flow. | Keep. |
| `scripts/export_mcp_inventory.py` | 3 | `keep-local` | Used for MCP inventory/export operations. | Keep until alternative inventory flow exists. |
| `scripts/local_prod_checklist.sh` | 13 | `keep-local` | Explicitly used by local production runbook checks. | Keep. |
| `scripts/mcp_health_summary.py` | 40 | `keep-local` | Core health summary used in gates and operations. | Keep. |
| `scripts/render_unclassified_decision_report.py` | 631 | `keep-local` | High reference footprint in current migration workflow. | Keep; migrate only with full report pipeline replacement. |
| `scripts/restore_hive_state.sh` | 6 | `keep-local` | Restore path pairs with backup safety lane. | Keep until backup/restore redesign. |
| `scripts/setup_local_pro.sh` | 1 | `keep-local` | One-shot local production bootstrap command referenced by runbook. | Keep as operator shortcut. |
| `scripts/telegram_chat_id_probe.py` | 4 | `keep-local` | Used for Telegram alert/chat-id bootstrap. | Keep. |
| `scripts/telegram_operator_signoff.py` | 6 | `keep-local` | Used in operator signoff flow and runbooks. | Keep. |
| `scripts/validate_backlog_markdown.py` | 36 | `keep-local` | Backlog guardrail validator used in CI/ops checks. | Keep. |
| `scripts/validate_factory_config.sh` | 1 | `keep-local` | Factory bootstrap validator referenced by `bootstrap_autonomous_factory.sh`. | Keep until replacement validator is available. |

## `scripts/upstream_*` per-file table (round 2, provisional)

Current rule for this round:

- all files are `keep-local-provisional` because the upstream migration/replay
  process in this fork still depends on these commands and wrappers.

| Path | Ref hits | Decision | Rationale | Replacement / Migration |
| --- | ---: | --- | --- | --- |
| `scripts/upstream_delta_status.py` | 11 | `keep-local-provisional` | Active upstream drift reporting utility. | Keep until replay workflow is replaced. |
| `scripts/upstream_landing_branch_bootstrap.sh` | 7 | `keep-local-provisional` | Landing-branch bootstrap for controlled replay. | Keep until landing branch workflow is retired. |
| `scripts/upstream_landing_branch_probe.sh` | 3 | `keep-local-provisional` | Probe helper for landing-branch readiness. | Keep while landing strategy is active. |
| `scripts/upstream_overlap_batch_a_apply.sh` | 6 | `keep-local-provisional` | Batch A replay apply helper. | Keep until overlap replay is closed. |
| `scripts/upstream_overlap_batch_a_bundle_apply.sh` | 8 | `keep-local-provisional` | Batch A bundle apply path used in migration. | Keep while bundle replay remains in use. |
| `scripts/upstream_overlap_batch_a_conflict_probe.sh` | 1 | `keep-local-provisional` | Conflict probe used during batch A triage. | Keep for replay debugging. |
| `scripts/upstream_overlap_batch_a_dependency_bundle.sh` | 2 | `keep-local-provisional` | Batch A dependency bundle generator. | Keep while dependency bundling is needed. |
| `scripts/upstream_overlap_batch_a_export.sh` | 1 | `keep-local-provisional` | Batch A export helper. | Keep for reproducible exports. |
| `scripts/upstream_overlap_batch_a_file_probe.sh` | 1 | `keep-local-provisional` | File probe utility for batch A. | Keep while batch A review is active. |
| `scripts/upstream_overlap_batch_a_focus_map.sh` | 1 | `keep-local-provisional` | Focus map generator for batch A lane selection. | Keep during lane review. |
| `scripts/upstream_overlap_batch_a_focus_patch.py` | 1 | `keep-local-provisional` | Patch helper for batch A focused replay. | Keep while focused replay exists. |
| `scripts/upstream_overlap_batch_a_focus_probe.sh` | 1 | `keep-local-provisional` | Focus probe helper for batch A. | Keep during focused replay checks. |
| `scripts/upstream_overlap_batch_a_hotspots_bundle.sh` | 3 | `keep-local-provisional` | Hotspot bundling helper for batch A risk areas. | Keep while hotspot flow exists. |
| `scripts/upstream_overlap_batch_a_integration_probe.sh` | 3 | `keep-local-provisional` | Integration probe for batch A replay. | Keep until replay completion. |
| `scripts/upstream_overlap_batch_a_landing_integrate.sh` | 1 | `keep-local-provisional` | Landing integration helper for batch A. | Keep while landing integration strategy is active. |
| `scripts/upstream_overlap_batch_a_landing_rehearsal.sh` | 3 | `keep-local-provisional` | Rehearsal helper for batch A landing. | Keep for safe rehearsal flow. |
| `scripts/upstream_overlap_batch_b_bundle.sh` | 2 | `keep-local-provisional` | Batch B bundle generator. | Keep while batch B replay remains open. |
| `scripts/upstream_overlap_batch_b_bundle_apply.sh` | 6 | `keep-local-provisional` | Batch B bundle apply helper. | Keep while replay is active. |
| `scripts/upstream_overlap_batch_b_dependency_bundle.sh` | 2 | `keep-local-provisional` | Batch B dependency bundle helper. | Keep while dependency bundling is required. |
| `scripts/upstream_overlap_batch_b_export.sh` | 2 | `keep-local-provisional` | Batch B export helper. | Keep for reproducibility. |
| `scripts/upstream_overlap_batch_b_landing_rehearsal.sh` | 3 | `keep-local-provisional` | Batch B landing rehearsal helper. | Keep while landing rehearsal is used. |
| `scripts/upstream_overlap_batch_c_bundle.sh` | 2 | `keep-local-provisional` | Batch C bundle generator. | Keep while batch C replay remains open. |
| `scripts/upstream_overlap_batch_c_bundle_apply.sh` | 6 | `keep-local-provisional` | Batch C bundle apply helper. | Keep while replay is active. |
| `scripts/upstream_overlap_batch_c_dependency_bundle.sh` | 2 | `keep-local-provisional` | Batch C dependency bundle helper. | Keep during staged replay. |
| `scripts/upstream_overlap_batch_c_export.sh` | 2 | `keep-local-provisional` | Batch C export helper. | Keep for deterministic export flow. |
| `scripts/upstream_overlap_batch_c_landing_rehearsal.sh` | 3 | `keep-local-provisional` | Batch C landing rehearsal helper. | Keep while landing rehearsal is required. |
| `scripts/upstream_replay_apply_probe.sh` | 3 | `keep-local-provisional` | Replay apply probe used in guard-railed migration. | Keep until replay pipeline closure. |
| `scripts/upstream_replay_bundle.sh` | 5 | `keep-local-provisional` | Replay bundle orchestration helper. | Keep while bundle replay is active. |
| `scripts/upstream_replay_compat_report.sh` | 3 | `keep-local-provisional` | Replay compatibility reporting helper. | Keep for compatibility evidence. |
| `scripts/upstream_sync_preflight.sh` | 14 | `keep-local-provisional` | Canonical preflight gate now includes destructive-lane guardrail. | Keep as required pre-apply gate. |
| `scripts/upstream_sync_regression_gate.sh` | 18 | `keep-local-provisional` | Canonical post-apply regression gate (`smoke/full`). | Keep as required post-apply gate. |
| `scripts/upstream_sync_watch.sh` | 4 | `keep-local-provisional` | Drift watch/report generator referenced by workflow docs. | Keep for upstream monitoring. |

## `scripts/check_*` per-file table (round 3)

Current rule for this round:

- all files are `keep-local-provisional` because they implement guardrail and
  contract checks that are currently required by acceptance and migration
  workflows.

| Path | Ref hits | Decision | Rationale | Replacement / Migration |
| --- | ---: | --- | --- | --- |
| `scripts/check_acceptance_docs_navigation.py` | 59 | `keep-local-provisional` | Validates docs navigation marker contract for acceptance flow. | Keep until acceptance docs contract is replaced. |
| `scripts/check_acceptance_gate_toggles_sync.py` | 18 | `keep-local-provisional` | Ensures acceptance gate toggles stay in sync. | Keep while acceptance toggles contract is active. |
| `scripts/check_acceptance_guardrail_marker_set_sync.py` | 13 | `keep-local-provisional` | Verifies marker-set parity across guardrail checkers. | Keep until guardrail marker framework is retired. |
| `scripts/check_acceptance_guardrails_sync.py` | 16 | `keep-local-provisional` | Canonical acceptance guardrail consistency checker. | Keep as long as guardrail set is mandatory. |
| `scripts/check_acceptance_preset_contract_sync.py` | 15 | `keep-local-provisional` | Preset command contract checker used in ops flow. | Keep until preset layer is replaced. |
| `scripts/check_acceptance_preset_smoke_determinism.sh` | 19 | `keep-local-provisional` | Smoke determinism checker for preset matrix. | Keep while preset matrix remains in use. |
| `scripts/check_acceptance_runbook_sanity_sync.py` | 27 | `keep-local-provisional` | Enforces runbook command-set alignment with implemented scripts. | Keep as runbook sync gate. |
| `scripts/check_acceptance_self_check_test_bundle_sync.py` | 18 | `keep-local-provisional` | Ensures self-check pytest bundle remains complete/consistent. | Keep until self-check bundle contract changes. |
| `scripts/check_backlog_archive_index.py` | 16 | `keep-local-provisional` | Backlog archive index integrity checker. | Keep while backlog archive artifacts are active. |
| `scripts/check_backlog_status_artifacts_index.py` | 17 | `keep-local-provisional` | Verifies backlog status artifact index contract. | Keep as long as backlog artifacts are generated. |
| `scripts/check_backlog_status_consistency.py` | 22 | `keep-local-provisional` | Core parser/validator consistency gate for backlog state. | Keep as mandatory backlog guardrail. |
| `scripts/check_backlog_status_drift.py` | 22 | `keep-local-provisional` | Detects drift between live backlog and latest artifact. | Keep while drift guardrail is required. |
| `scripts/check_backlog_status_json_contract.py` | 12 | `keep-local-provisional` | Verifies backlog JSON schema/contract stability. | Keep as API/automation contract gate. |
| `scripts/check_runbook_sync.py` | 26 | `keep-local-provisional` | Ensures runbook script references are valid. | Keep as runbook contract checker. |
| `scripts/check_runtime_parity.sh` | 37 | `keep-local-provisional` | Runtime parity gate for operational API surface. | Keep as required acceptance/regression check. |
| `scripts/check_unclassified_delta_decisions.py` | 637 | `keep-local-provisional` | High-usage decision register contract checker in migration process. | Keep until unclassified-delta flow is formally replaced. |
| `scripts/check_upstream_bucket_contract_sync.py` | 8 | `keep-local-provisional` | Validates upstream bucket contract consistency. | Keep while upstream bucket governance is active. |

## `scripts/acceptance_*` per-file table (round 4)

Current rule for this round:

- all files are `keep-local-provisional` because they implement acceptance gate,
  reporting, and maintenance contracts used by release and weekly operations.

| Path | Ref hits | Decision | Rationale | Replacement / Migration |
| --- | ---: | --- | --- | --- |
| `scripts/acceptance_gate_presets.sh` | 82 | `keep-local-provisional` | Canonical preset wrapper (`fast/strict/full/full-deep`) used across runbooks and checks. | Keep until preset orchestration is replaced. |
| `scripts/acceptance_gate_presets_smoke.sh` | 22 | `keep-local-provisional` | Preset smoke matrix helper used for determinism checks. | Keep while preset smoke contract is active. |
| `scripts/acceptance_ops_summary.py` | 33 | `keep-local-provisional` | Produces ops summary artifacts consumed by operators and docs. | Keep until summary artifact flow is replaced. |
| `scripts/acceptance_report_artifact.py` | 12 | `keep-local-provisional` | Generates acceptance report artifact payloads. | Keep while report artifact contract exists. |
| `scripts/acceptance_report_digest.py` | 16 | `keep-local-provisional` | Builds digest views from acceptance report artifacts. | Keep until digest flow replacement is adopted. |
| `scripts/acceptance_report_hygiene.py` | 19 | `keep-local-provisional` | Maintains acceptance report archive/index hygiene. | Keep while artifact retention policy is active. |
| `scripts/acceptance_report_regression_guard.py` | 13 | `keep-local-provisional` | Guards regression status from acceptance report data. | Keep until equivalent regression guard exists. |
| `scripts/acceptance_scheduler_snapshot.sh` | 18 | `keep-local-provisional` | Captures scheduler/log snapshots for ops troubleshooting. | Keep as operator diagnostics helper. |
| `scripts/acceptance_toolchain_self_check.sh` | 103 | `keep-local-provisional` | Central self-check entrypoint for acceptance toolchain contracts. | Keep as mandatory acceptance guardrail. |
| `scripts/acceptance_toolchain_self_check_deep.sh` | 23 | `keep-local-provisional` | Extended self-check profile used by deep acceptance flow. | Keep while deep profile is enabled. |
| `scripts/acceptance_weekly_maintenance.sh` | 22 | `keep-local-provisional` | Weekly maintenance orchestrator for acceptance trend artifacts. | Keep until weekly automation is redesigned. |

## `scripts/autonomous_*` per-file table (round 5)

Current rule for this round:

- all files are `keep-local-provisional` because they implement autonomous loop
  orchestration and runtime health/remediation flow used in this fork.

| Path | Ref hits | Decision | Rationale | Replacement / Migration |
| --- | ---: | --- | --- | --- |
| `scripts/autonomous_acceptance_gate.sh` | 55 | `keep-local-provisional` | Canonical acceptance gate runner for autonomous operations. | Keep while autonomous acceptance flow is active. |
| `scripts/autonomous_delivery_e2e_smoke.py` | 29 | `keep-local-provisional` | E2E smoke for delivery path and template/real repo scenarios. | Keep until alternative delivery E2E gate exists. |
| `scripts/autonomous_loop_tick.sh` | 21 | `keep-local-provisional` | Loop tick wrapper used by scheduler/operator automation. | Keep while loop scheduler contract remains. |
| `scripts/autonomous_operator_profile.sh` | 87 | `keep-local-provisional` | High-usage operator profile entrypoint for autonomous flow. | Keep until operator profile layer is replaced. |
| `scripts/autonomous_ops_drill.sh` | 26 | `keep-local-provisional` | Operational drill helper for autonomous readiness checks. | Keep while drill workflow is used. |
| `scripts/autonomous_ops_health_check.sh` | 41 | `keep-local-provisional` | Health-check orchestrator for autonomous operation stack. | Keep as runtime guardrail until replacement. |
| `scripts/autonomous_remediate_stale_runs.sh` | 28 | `keep-local-provisional` | Automated stale-run remediation helper. | Keep while stale-run remediation path is active. |
| `scripts/autonomous_scheduler_daemon.py` | 13 | `keep-local-provisional` | Scheduler daemon for autonomous cycle execution. | Keep until scheduler architecture is replaced. |

## `scripts/backlog_*` per-file table (round 6)

Current rule for this round:

- all files are `keep-local-provisional` because they implement backlog status,
  artifact generation, and archive hygiene contracts used by ops automation.

| Path | Ref hits | Decision | Rationale | Replacement / Migration |
| --- | ---: | --- | --- | --- |
| `scripts/backlog_archive_hygiene.py` | 20 | `keep-local-provisional` | Maintains archive/index hygiene for backlog snapshots. | Keep while backlog archive lifecycle is active. |
| `scripts/backlog_archive_snapshot.py` | 6 | `keep-local-provisional` | Creates archive snapshots for backlog history. | Keep until snapshot strategy is replaced. |
| `scripts/backlog_status.py` | 114 | `keep-local-provisional` | Canonical backlog parser/status source for many checks and reports. | Keep as core backlog contract entrypoint. |
| `scripts/backlog_status_artifact.py` | 29 | `keep-local-provisional` | Produces machine-readable backlog status artifacts. | Keep while artifact pipeline is active. |
| `scripts/backlog_status_hygiene.py` | 25 | `keep-local-provisional` | Cleans/rotates backlog artifact history and index. | Keep until artifact hygiene is redesigned. |

## `scripts/google_*` per-file table (round 7)

Current rule for this round:

- all files are `keep-local-provisional` because they implement Google OAuth
  refresh/canary/smoke operations used by MCP health and production runbooks.

| Path | Ref hits | Decision | Rationale | Replacement / Migration |
| --- | ---: | --- | --- | --- |
| `scripts/google_mcp_canary.py` | 5 | `keep-local-provisional` | Google canary runner used for periodic integration verification. | Keep until Google canary path is replaced. |
| `scripts/google_mcp_smoke_test.py` | 6 | `keep-local-provisional` | Google MCP smoke test command referenced in runbook checks. | Keep while smoke verification remains required. |
| `scripts/google_oauth_token_manager.py` | 10 | `keep-local-provisional` | OAuth auth-url/exchange manager for token lifecycle. | Keep as long as current OAuth bootstrap flow is used. |
| `scripts/google_token_auto_refresh.sh` | 11 | `keep-local-provisional` | Manual/ops refresh helper tied to runtime token updates. | Keep while token refresh SOP uses this entrypoint. |
| `scripts/google_token_refresher_daemon.py` | 4 | `keep-local-provisional` | Daemon refresh worker for containerized token rotation. | Keep until refresher architecture is replaced. |

## `scripts/hive_*` per-file table (round 8)

Current rule for this round:

- all files are `keep-local-provisional` because they are container-first
  operational wrappers used heavily in the local-prod and CI/ops workflow.

| Path | Ref hits | Decision | Rationale | Replacement / Migration |
| --- | ---: | --- | --- | --- |
| `scripts/hive_hot_sync.sh` | 5 | `keep-local-provisional` | Fast dev sync helper for containerized runtime loop. | Keep while hot-sync workflow is supported. |
| `scripts/hive_model_profiles.sh` | 1 | `keep-local-provisional` | Model profile helper used for provider/runtime presets. | Keep until model profile handling is redesigned. |
| `scripts/hive_ops_preflight.sh` | 9 | `keep-local-provisional` | Preflight aggregator for ops checks before risky operations. | Keep while preflight contract remains active. |
| `scripts/hive_ops_run.sh` | 288 | `keep-local-provisional` | Core container-first command wrapper used across scripts/runbooks. | Keep as foundational ops runtime wrapper. |

## `scripts/verify_*` per-file table (round 9)

Current rule for this round:

- file is `keep-local-provisional` because it provides access-stack validation
  used directly in production runbook and acceptance checks.

| Path | Ref hits | Decision | Rationale | Replacement / Migration |
| --- | ---: | --- | --- | --- |
| `scripts/verify_access_stack.sh` | 42 | `keep-local-provisional` | Core access-stack verification (`GitHub/Google/Telegram/Redis/Postgres`) for local-prod workflow. | Keep until equivalent end-to-end access validation is introduced. |

## Scheduler lane per-file table (round 10)

Current rule for this round:

- all files are `keep-local-provisional` because they provide install/status/
  uninstall lifecycle for scheduler profiles (`acceptance`, `weekly`,
  `autonomous`, `google-canary`, `google-refresh`) across cron/launchd modes.

| Path | Ref hits | Decision | Rationale | Replacement / Migration |
| --- | ---: | --- | --- | --- |
| `scripts/install_acceptance_gate_cron.sh` | 8 | `keep-local-provisional` | Installs cron scheduler for acceptance gate. | Keep until cron scheduler path is retired. |
| `scripts/install_acceptance_gate_launchd.sh` | 15 | `keep-local-provisional` | Installs launchd scheduler for acceptance gate. | Keep until launchd path is retired. |
| `scripts/install_acceptance_weekly_cron.sh` | 6 | `keep-local-provisional` | Installs weekly acceptance maintenance cron job. | Keep while weekly cron flow is supported. |
| `scripts/install_acceptance_weekly_launchd.sh` | 6 | `keep-local-provisional` | Installs weekly acceptance maintenance launchd job. | Keep while weekly launchd flow is supported. |
| `scripts/install_autonomous_loop_cron.sh` | 6 | `keep-local-provisional` | Installs autonomous loop cron scheduler. | Keep while autonomous cron profile is available. |
| `scripts/install_autonomous_loop_launchd.sh` | 5 | `keep-local-provisional` | Installs autonomous loop launchd scheduler. | Keep while autonomous launchd profile is available. |
| `scripts/install_google_canary_cron.sh` | 0 | `keep-local-provisional` | Optional install helper for Google canary cron profile. | Keep until Google canary scheduler policy is finalized. |
| `scripts/install_google_canary_launchd.sh` | 0 | `keep-local-provisional` | Optional install helper for Google canary launchd profile. | Keep until Google canary scheduler policy is finalized. |
| `scripts/install_google_refresh_launchd.sh` | 0 | `keep-local-provisional` | Optional install helper for Google refresh launchd profile. | Keep until Google refresh scheduler architecture is finalized. |
| `scripts/status_acceptance_gate_cron.sh` | 8 | `keep-local-provisional` | Status probe for acceptance gate cron scheduler. | Keep with acceptance cron lifecycle scripts. |
| `scripts/status_acceptance_gate_launchd.sh` | 15 | `keep-local-provisional` | Status probe for acceptance gate launchd scheduler. | Keep with acceptance launchd lifecycle scripts. |
| `scripts/status_acceptance_weekly_cron.sh` | 7 | `keep-local-provisional` | Status probe for weekly acceptance cron scheduler. | Keep with weekly cron lifecycle scripts. |
| `scripts/status_acceptance_weekly_launchd.sh` | 7 | `keep-local-provisional` | Status probe for weekly acceptance launchd scheduler. | Keep with weekly launchd lifecycle scripts. |
| `scripts/status_autonomous_loop_cron.sh` | 7 | `keep-local-provisional` | Status probe for autonomous loop cron scheduler. | Keep with autonomous cron lifecycle scripts. |
| `scripts/status_autonomous_loop_launchd.sh` | 9 | `keep-local-provisional` | Status probe for autonomous loop launchd scheduler. | Keep with autonomous launchd lifecycle scripts. |
| `scripts/status_google_canary_cron.sh` | 0 | `keep-local-provisional` | Optional status probe for Google canary cron profile. | Keep until Google canary scheduler policy is finalized. |
| `scripts/status_google_canary_launchd.sh` | 0 | `keep-local-provisional` | Optional status probe for Google canary launchd profile. | Keep until Google canary scheduler policy is finalized. |
| `scripts/status_google_refresh_launchd.sh` | 0 | `keep-local-provisional` | Optional status probe for Google refresh launchd profile. | Keep until Google refresh scheduler architecture is finalized. |
| `scripts/uninstall_acceptance_gate_cron.sh` | 5 | `keep-local-provisional` | Uninstall helper for acceptance gate cron scheduler. | Keep with acceptance cron lifecycle scripts. |
| `scripts/uninstall_acceptance_gate_launchd.sh` | 10 | `keep-local-provisional` | Uninstall helper for acceptance gate launchd scheduler. | Keep with acceptance launchd lifecycle scripts. |
| `scripts/uninstall_acceptance_weekly_cron.sh` | 5 | `keep-local-provisional` | Uninstall helper for weekly acceptance cron scheduler. | Keep with weekly cron lifecycle scripts. |
| `scripts/uninstall_acceptance_weekly_launchd.sh` | 7 | `keep-local-provisional` | Uninstall helper for weekly acceptance launchd scheduler. | Keep with weekly launchd lifecycle scripts. |
| `scripts/uninstall_autonomous_loop_cron.sh` | 5 | `keep-local-provisional` | Uninstall helper for autonomous loop cron scheduler. | Keep with autonomous cron lifecycle scripts. |
| `scripts/uninstall_autonomous_loop_launchd.sh` | 6 | `keep-local-provisional` | Uninstall helper for autonomous loop launchd scheduler. | Keep with autonomous launchd lifecycle scripts. |
| `scripts/uninstall_google_canary_cron.sh` | 0 | `keep-local-provisional` | Optional uninstall helper for Google canary cron profile. | Keep until Google canary scheduler policy is finalized. |
| `scripts/uninstall_google_canary_launchd.sh` | 0 | `keep-local-provisional` | Optional uninstall helper for Google canary launchd profile. | Keep until Google canary scheduler policy is finalized. |
| `scripts/uninstall_google_refresh_launchd.sh` | 0 | `keep-local-provisional` | Optional uninstall helper for Google refresh launchd profile. | Keep until Google refresh scheduler architecture is finalized. |

## `scripts/tests/**` lane policy note (round 11, lane-level)

Lane decision:

- `scripts/tests/**` remains `keep-local` as a lane-level policy.

Rationale:

- test files are tightly coupled to retained operational scripts and contracts;
- deleting tests without corresponding script retirement would reduce safety
  coverage for migration and acceptance gates.

Replay exclusion rule:

- no destructive apply for `scripts/tests/**` is allowed unless:
  1. the paired operational script lane is explicitly retired by owner decision;
  2. replacement tests are present and passing in the post-apply full gate.

## Post-wave handoff

Wave 14 lane decisions are finalized for workflows + full `scripts/**`.

Handoff constraints:

1. No destructive apply without explicit owner allowlist.
2. Any future destructive replay must pass:
   - pre-apply guardrail (`check_upstream_destructive_lanes.py`);
   - post-apply full gate (`HIVE_UPSTREAM_SYNC_GATE_PROFILE=full`).

This keeps high-impact lanes (`acceptance_*`, `autonomous_*`, `check_*`) blocked
until lower-risk misc scripts are classified first.

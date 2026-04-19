# Acceptance Automation Map

## Purpose

Operator-facing map of acceptance automation scripts, cadence, and typical usage order.
Container-first path is preferred for portable local-prod operations.

## Container-First Entry Points

- `scripts/hive_ops_run.sh`
  - Wrapper for one-shot commands via `docker compose --profile ops run --rm --no-deps hive-ops ...`.
  - Uses persistent host caches (`.cache/uv`, `.cache/uvproj`) to avoid cold-start penalty on repeated runs.
- `scripts/hive_ops_preflight.sh`
  - One-command preflight chain for backlog validation, docs/runbook checks, upstream contract checks,
    runtime parity, and backlog status artifact refresh.
  - Supports env controls:
    - `HIVE_OPS_PREFLIGHT_BASE_URL`
    - `HIVE_OPS_PREFLIGHT_BACKLOG_KEEP`
    - `HIVE_OPS_PREFLIGHT_BACKLOG_HYGIENE_APPLY`
    - `HIVE_OPS_PREFLIGHT_BUILD_IMAGE`
- `scripts/autonomous_operator_profile.sh`
  - Unified operator wrapper for daily/deep/dry-run autonomous workflows:
    - `daily`: preflight -> stale-runs remediation (apply) -> strict acceptance gate -> ops summary
      (with operator-safe health overrides for local container runtime:
      `ALLOW_LOOP_STALE=true`, `MAX_NO_PROGRESS_PROJECTS=1`)
      and remediation controls:
      `HIVE_OPERATOR_AUTO_REMEDIATE_STALE=true|false`,
      `HIVE_OPERATOR_REMEDIATE_ACTION=escalated|failed`.
    - `deep`: preflight -> deep self-check -> [optional stale-runs remediation] -> full-deep acceptance gate -> ops summary
      (`HIVE_OPERATOR_DEEP_AUTO_REMEDIATE_STALE=true|false`, default `false`)
    - `dry-run`: safe preview of strict/full-deep gate env plans + current ops summary
  - Operator health profiles:
    - `prod` (default): `0/1/allow_stale=true` for `stuck/no_progress/loop_stale`
    - `strict`: `0/0/allow_stale=false`
    - `relaxed`: `2/2/allow_stale=true`
  - CLI remediation overrides (run-scoped, higher priority than env):
    - `--remediate`
    - `--no-remediate`
    - `--no-remediation` (alias)
    - `--daily-remediate` / `--no-daily-remediate`
    - `--deep-remediate` / `--no-deep-remediate`
    - `--remediate-action <escalated|failed>`
    - `--project-health-profile <prod|strict|relaxed>`
    - `--skip-preflight`
    - `--skip-self-check` (deep mode)
    - `--ops-summary-only`
    - `--acceptance-preset <fast|strict|full|full-deep>`
    - `--acceptance-extra-args "<...>"`
  - Project-scoped operation:
    - `--project <id>` (maps to acceptance gate project context)
  - Container-network aware API target for summary:
    - `--base-url http://hive-core:8787` (default)

## Core Gate

- `scripts/autonomous_acceptance_gate.sh`
  - End-to-end acceptance gate for parity/health/remediation/reporting/telegram checks.
  - Supports strict toggles: history enforcement, JSON summary, optional pre self-check,
    optional autonomous delivery e2e smoke.
- `scripts/autonomous_delivery_e2e_smoke.py`
  - Container-first autonomous delivery smoke scenario runner.
  - Covers:
    - `real_repo` flow (existing project/repo),
    - `template_repo` flow (temporary template project).
  - Emits trace fields (`task_id`, `run_id`, `terminal_status`, `report_endpoint`, optional `pr_url`).
- `scripts/acceptance_gate_presets.sh`
  - Preset launcher for gate:
    - `fast` (quick local smoke),
    - `strict` (history enforcement + JSON summary),
    - `full` (strict + self-check + docs-nav check),
    - `full-deep` (full + preset smoke + delivery e2e smoke + self-check runtime parity).
  - Supports safe preview mode: `--print-env-only`.
  - Error behavior:
    - unknown mode -> non-zero + usage output;
    - missing `--project` value -> non-zero + explicit error.

## Artifact Lifecycle

- `scripts/acceptance_report_artifact.py`
  - Writes acceptance report JSON artifacts and updates `latest.json`.
- `scripts/acceptance_report_hygiene.py`
  - Prune-preview/apply for acceptance artifacts.
  - Rebuilds `docs/ops/acceptance-reports/INDEX.md`.
- `scripts/acceptance_report_digest.py`
  - Generates pass/fail digest from historical artifacts.
- `scripts/acceptance_report_regression_guard.py`
  - Enforces historical thresholds (`max-fail`, `min-pass-rate`).

## Operator Snapshots

- `scripts/acceptance_ops_summary.py`
  - Compact status from latest artifact and digest,
    plus backlog status snapshot fields (`tasks_total`, `in_progress`, `focus_refs`).
- Backlog status auto-refresh sequence:
  - `uv run python scripts/backlog_status_artifact.py`
  - `uv run python scripts/backlog_status_hygiene.py --keep 50`
  - `uv run python scripts/check_backlog_status_drift.py`
  - `uv run python scripts/check_backlog_status_artifacts_index.py`
- Backlog status auto-refresh sequence (container-first equivalent):
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_artifact.py`
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_hygiene.py --keep 50 --yes`
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_drift.py`
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_artifacts_index.py`
- `scripts/backlog_status.py`
  - Backlog execution snapshot in text mode and machine-readable mode (`--json`).
- `scripts/backlog_status_artifact.py`
  - Writes backlog status snapshots to `docs/ops/backlog-status/` (`latest.json` + timestamped files).
- `scripts/backlog_status_hygiene.py`
  - Applies safe preview/apply prune flow and rebuilds `docs/ops/backlog-status/INDEX.md`.
- `scripts/acceptance_scheduler_snapshot.sh`
  - Hourly/weekly + autonomous scheduler status (launchd + cron + docker sidecar) with optional log tails.

## Weekly Maintenance

- `scripts/acceptance_weekly_maintenance.sh`
  - One-command digest + hygiene + regression guard.
- `scripts/install_acceptance_weekly_launchd.sh`
- `scripts/status_acceptance_weekly_launchd.sh`
- `scripts/uninstall_acceptance_weekly_launchd.sh`
- `scripts/install_acceptance_weekly_cron.sh`
- `scripts/status_acceptance_weekly_cron.sh`
- `scripts/uninstall_acceptance_weekly_cron.sh`
  - Scheduler wrappers for weekly cadence (launchd + cron fallback).

## Hourly Gate Scheduler

- `scripts/install_acceptance_gate_launchd.sh`
- `scripts/status_acceptance_gate_launchd.sh`
- `scripts/uninstall_acceptance_gate_launchd.sh`
- `scripts/install_acceptance_gate_cron.sh`
- `scripts/status_acceptance_gate_cron.sh`
- `scripts/uninstall_acceptance_gate_cron.sh`
  - Scheduler wrappers for periodic acceptance gate (launchd + cron fallback).

## Autonomous Loop Scheduler

- `scripts/autonomous_scheduler_daemon.py`
  - Container-native scheduler loop for:
    - autonomous `run-cycle/report` ticks,
    - lightweight acceptance probes (`/api/health` + `/api/autonomous/ops/status`).
- `scripts/install_autonomous_loop_launchd.sh`
- `scripts/status_autonomous_loop_launchd.sh`
- `scripts/uninstall_autonomous_loop_launchd.sh`
- `scripts/install_autonomous_loop_cron.sh`
- `scripts/status_autonomous_loop_cron.sh`
- `scripts/uninstall_autonomous_loop_cron.sh`
  - Scheduler wrappers for autonomous loop cadence (launchd + cron fallback).
- `docker compose up -d hive-scheduler`
  - Preferred persistent scheduler on hosts where launchd/cron are unreliable.
  - Container-only baseline for portable deployments across machines.

## Toolchain Integrity

- `scripts/acceptance_toolchain_self_check.sh`
  - Shell syntax checks + runbook sync + unit tests + ops summary + scheduler snapshot.
  - Includes backlog status auto-refresh step before drift check to avoid false-positive mismatch after fresh backlog edits.
  - Optional deep mode:
    - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true ./scripts/acceptance_toolchain_self_check.sh`
      to include preset matrix smoke (`fast|strict|full` + project override).
    - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh`
      to include live API runtime parity check against running core.
    - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh`
      to run full deep self-check profile.
- `scripts/acceptance_toolchain_self_check_deep.sh`
  - One-command wrapper for full deep self-check profile
    (`preset_smoke + runtime_parity`).
- `scripts/check_acceptance_gate_toggles_sync.py`
  - Guardrail check for toggle drift between
    `scripts/autonomous_acceptance_gate.sh` and `docs/LOCAL_PROD_RUNBOOK.md`.
- `scripts/check_acceptance_docs_navigation.py`
  - Guardrail check for required cross-links and key acceptance markers in docs.
- `scripts/check_backlog_archive_index.py`
  - Guardrail check for backlog archive consistency:
    - no `unknown` timestamps in `archive/INDEX.md`,
    - all snapshot files are indexed,
    - no stale snapshot refs in index.
- `scripts/check_acceptance_preset_contract_sync.py`
  - Guardrail check for preset contract sync across:
    `acceptance_gate_presets.sh`, `acceptance_gate_presets_smoke.sh`, and acceptance map docs.
- `scripts/check_acceptance_preset_smoke_determinism.sh`
  - Runtime shell check: smoke matrix stays deterministic under contaminated `HIVE_ACCEPTANCE_*` env.
- `scripts/check_acceptance_guardrails_sync.py`
  - Guardrail sync check: required checker scripts must be present in both
    `acceptance_toolchain_self_check.sh` and this acceptance automation map.
- `scripts/check_acceptance_self_check_test_bundle_sync.py`
  - Guardrail sync check: required acceptance test modules must stay in
    `acceptance_toolchain_self_check.sh` pytest bundle.
- `scripts/check_acceptance_guardrail_marker_set_sync.py`
  - Guardrail sync check: marker sets between guardrails checker and docs-nav checker remain aligned.
- `scripts/check_backlog_status_consistency.py`
  - Guardrail sync check: parser-level consistency between
    `scripts/backlog_status.py` and `scripts/validate_backlog_markdown.py`.
- `scripts/check_backlog_status_json_contract.py`
  - Guardrail sync check: JSON contract for
    `scripts/backlog_status.py --json` remains stable and machine-readable.
- `scripts/check_backlog_status_drift.py`
  - Guardrail sync check: compares live backlog status (`backlog_status.py --json`)
    against `docs/ops/backlog-status/latest.json` after markdown validator passes.
- `scripts/check_backlog_status_artifacts_index.py`
  - Guardrail sync check: `docs/ops/backlog-status/INDEX.md` matches existing
    `backlog-status-*.json` files (no missing/stale references).
- `scripts/check_acceptance_runbook_sanity_sync.py`
  - Guardrail sync check: runbook includes all key acceptance sanity-check commands.
- `scripts/tests/test_check_runbook_sync.py`
- `scripts/tests/test_acceptance_report_hygiene.py`
  - Unit tests for acceptance automation helper logic.

## Recommended Cadence

1. Before rollout (container-first): `./scripts/hive_ops_preflight.sh`
2. Deep gate readiness: `./scripts/acceptance_toolchain_self_check.sh`
3. Continuous: `hive-scheduler` sidecar (`autonomous_interval` + `acceptance_interval`)
4. Hourly/weekly fallback: launchd or cron wrappers (legacy/optional)
5. On-demand diagnostics: `acceptance_scheduler_snapshot.sh` and `acceptance_ops_summary.py`

## Quick Start

1. Container preflight baseline:
   - `./scripts/hive_ops_preflight.sh`
2. Operator daily profile (recommended):
   - `./scripts/autonomous_operator_profile.sh --mode daily --project <project-id>`
3. Operator deep profile (extended):
   - `./scripts/autonomous_operator_profile.sh --mode deep --project <project-id>`
4. Operator dry-run profile (safe preview):
   - `./scripts/autonomous_operator_profile.sh --mode dry-run --project <project-id>`
5. Quick smoke:
   - `./scripts/acceptance_gate_presets.sh fast`
6. Strict validation:
   - `./scripts/acceptance_gate_presets.sh strict`
7. Full strict with extended checks:
   - `./scripts/acceptance_gate_presets.sh full`
8. Full deep strict profile:
   - `./scripts/acceptance_gate_presets.sh full-deep`
9. Deep self-check with live parity:
   - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh`
10. Full deep self-check profile:
   - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh`
11. Full deep self-check wrapper:
   - `./scripts/acceptance_toolchain_self_check_deep.sh`

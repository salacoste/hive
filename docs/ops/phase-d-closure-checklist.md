# Phase D Closure Checklist (Ops Recovery Readiness)

Source of truth: `docs/autonomous-factory/13-master-implementation-plan.md` -> `Phase D`.

## Exit Criteria

1. Stale/no-progress failures are detectable and remediable.
2. Backup and restore dry-run are reproducible.
3. Unified ops drill is green.
4. Scheduler routine is documented with explicit fallback/troubleshooting.

## Command Checklist

```bash
# 1) baseline ops health
./scripts/autonomous_ops_health_check.sh

# 2) stale remediation (preview)
./scripts/autonomous_remediate_stale_runs.sh

# 3) stale remediation (apply, explicit confirm)
HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=false \
HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=true \
HIVE_AUTONOMOUS_REMEDIATE_MAX_RUNS=500 \
./scripts/autonomous_remediate_stale_runs.sh

# 4) recovery drill (health + backup + restore dry-run + loop smoke)
./scripts/autonomous_ops_drill.sh

# 5) scheduler status snapshot
./scripts/acceptance_scheduler_snapshot.sh
```

## Latest Closure Evidence

Date: `2026-04-10` (local run)

- Detected real stale backlog in ops status: `stuck_runs=223`, `no_progress_projects=223`.
- Applied remediation:
  - `selected_total=223`,
  - terminalized via `action=escalated`.
- Post-remediation health:
  - `./scripts/autonomous_ops_health_check.sh` -> `stuck_runs=0`, `no_progress_projects=0`, `ok`.
- Recovery drill:
  - `./scripts/autonomous_ops_drill.sh` -> `Drill summary: ok=5 failed=0`.
  - Includes fresh backup artifact + restore dry-run plan.

## Scheduler Routine Notes

- launchd wrappers were verified for install/uninstall/status control.
- On this host/path (`~/Documents/...`) launchd returns
  `Operation not permitted` when executing repo scripts.
- Runbook now contains explicit fallback:
  - keep launchd jobs uninstalled,
  - install cron wrappers for acceptance gate/weekly/autonomous loop,
  - keep manual ops cadence as emergency fallback.

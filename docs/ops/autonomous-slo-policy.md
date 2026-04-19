# Autonomous Loop SLO Policy

## Scope

This policy defines operator SLO thresholds and drill cadence for Hive autonomous execution.

## Health Profiles

`autonomous_ops_health_check.sh` supports profile-driven thresholds via `HIVE_AUTONOMOUS_HEALTH_PROFILE`:

- `local` / `dev` (default)
  - `max_stuck_runs=2`
  - `max_no_progress_projects=2`
  - `allow_loop_stale=true`
- `staging`
  - `max_stuck_runs=1`
  - `max_no_progress_projects=1`
  - `allow_loop_stale=false`
- `prod`
  - `max_stuck_runs=0`
  - `max_no_progress_projects=0`
  - `allow_loop_stale=false`

Explicit env overrides (`HIVE_AUTONOMOUS_HEALTH_MAX_*`, `HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE`) always win over profile defaults.

## Operational Thresholds

Runtime alert thresholds (from `/api/autonomous/ops/status`):

- `HIVE_AUTONOMOUS_STUCK_RUN_SECONDS` (default `1800`)
- `HIVE_AUTONOMOUS_NO_PROGRESS_SECONDS` (default `900`)
- `HIVE_AUTONOMOUS_LOOP_STALE_SECONDS` (default `600`)

Recommended values:

- local/dev: defaults are acceptable while iterating
- prod:
  - stuck: `900-1800` seconds
  - no-progress: `600-900` seconds
  - loop-stale: `300-600` seconds

## Drill Cadence

- Daily:
  - `./scripts/autonomous_ops_health_check.sh` (or cron/launchd equivalent)
- Weekly:
  - `./scripts/autonomous_ops_drill.sh`
- Before deploy / after incident:
  - `./scripts/check_runtime_parity.sh`
  - `./scripts/local_prod_checklist.sh`
  - `./scripts/autonomous_ops_drill.sh`

## Acceptance Criteria

A period is considered SLO-compliant when:

1. No unresolved `stuck_runs` above profile threshold.
2. No unresolved `no_progress_projects` above profile threshold.
3. Loop heartbeat is not stale unless profile explicitly allows it.
4. Runtime parity check passes after each deploy/rebuild.

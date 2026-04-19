# Phase A Closure Checklist (Runtime Stabilization)

Source of truth: `docs/autonomous-factory/13-master-implementation-plan.md` -> `Phase A`.

## Exit Criteria

1. Core health is stable.
2. Runtime parity check passes.
3. Acceptance toolchain self-check passes in full.

## Command Checklist

```bash
# 1) core health
curl -fsS http://localhost:${HIVE_CORE_PORT:-8787}/api/health

# 2) runtime contract parity
./scripts/check_runtime_parity.sh

# 3) full acceptance self-check
./scripts/acceptance_toolchain_self_check.sh
```

## Latest Closure Evidence

Date: `2026-04-10` (local run)

- `api/health`: `status=ok` and telegram bridge runtime status present.
- `check_runtime_parity.sh`: `runtime parity check passed`.
- `acceptance_toolchain_self_check.sh`: `ok=19 failed=0` (all enabled checks green).

## Notes

- Self-check includes backlog status auto-refresh before drift check:
  - `backlog_status_artifact.py`
  - `backlog_status_hygiene.py --keep 50`
- This prevents false-positive drift failures after fresh backlog edits.

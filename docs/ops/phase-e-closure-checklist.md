# Phase E Closure Checklist (Governance + Operator UX)

Source of truth: `docs/autonomous-factory/13-master-implementation-plan.md` -> `Phase E`.

## Exit Criteria

1. Backlog governance is deterministic (`single in_progress` while active wave, terminal-completion mode when all tasks are `done`, no drift).
2. Operator runbook and guardrail automation remain in sync.
3. Core acceptance summary is green for local production operation.
4. Go-live acceptance pack is assembled for operator sign-off.

## Command Checklist

```bash
# 1) backlog governance
uv run python scripts/validate_backlog_markdown.py
uv run python scripts/backlog_status.py --json --path docs/autonomous-factory/12-backlog-task-list.md
uv run python scripts/check_backlog_status_drift.py

# 2) runbook/guardrails sync
uv run python scripts/check_acceptance_runbook_sanity_sync.py
./scripts/acceptance_toolchain_self_check.sh

# 3) operational acceptance snapshot
uv run python scripts/mcp_health_summary.py --since-minutes 30
./scripts/autonomous_ops_health_check.sh
uv run python scripts/acceptance_ops_summary.py --json
```

## Latest Evidence Snapshot

Date: `2026-04-10` (local run)

- Backlog governance:
  - `tasks_total=107`,
  - `in_progress=[]`,
  - `focus_refs=[]`,
  - drift check `ok` (`in_sync`).
- Acceptance self-check:
  - `Self-check summary: ok=20 failed=0`.
- MCP required stack:
  - `mcp_health_summary`: `status=ok`, `5/5`.
- Ops health:
  - `stuck_runs=0`, `no_progress_projects=0`, status `ok`.
- Acceptance ops summary:
  - `backlog_drift_detected=False`,
  - `backlog_done_total=107`,
  - `backlog_todo_total=0`.

## Notes

- container-only scheduler baseline uses docker sidecar (`hive-scheduler`);
  host launchd/cron wrappers remain optional legacy fallback.
- Final closure requires explicit operator sign-off against go-live acceptance pack.

# Backlog Compaction Checklist

Use this checklist at the end of each execution wave to keep
`12-backlog-task-list.md` operational and easy to execute.

## Cadence

- Trigger: on wave closure or at least once per week.
- Owner: current operator on duty.

## Checklist

1. Validate structure and focus:
   - `uv run python scripts/validate_backlog_markdown.py`
2. Confirm active execution context:
   - `uv run python scripts/backlog_status.py`
3. Ensure no stale `in_progress` item remains without recent updates.
4. Move completed-wave evidence to archive:
   - `uv run python scripts/backlog_archive_snapshot.py`
   - `uv run python scripts/backlog_archive_hygiene.py`
5. If archive exceeds retention, run prune preview first:
   - `uv run python scripts/backlog_archive_hygiene.py --prune-keep 20`
6. Apply prune only after preview review:
   - `uv run python scripts/backlog_archive_hygiene.py --prune-keep 20 --yes`
7. Re-run acceptance gate:
   - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true ./scripts/autonomous_acceptance_gate.sh`
8. Update `Current Focus` to the next active task id and ensure exactly one `in_progress`.

## Exit Criteria

- Backlog validator passes.
- Acceptance gate is green.
- Archive index is up to date.

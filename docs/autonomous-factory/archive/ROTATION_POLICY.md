# Backlog Archive Rotation Policy

## Goal

Keep backlog archive useful and lightweight while preserving audit trail of completed waves.

## Snapshot Cadence

1. Run snapshot after each execution wave closure:
   - `uv run python scripts/backlog_archive_snapshot.py`
2. Run hygiene/index update after snapshot:
   - `uv run python scripts/backlog_archive_hygiene.py`

## Retention

- Default retention: keep latest **20** snapshots.
- Guardrail preview (non-destructive):
  - `uv run python scripts/backlog_archive_hygiene.py --prune-keep 20`
- Apply prune only after preview review:
  - `uv run python scripts/backlog_archive_hygiene.py --prune-keep 20 --yes`
- Never prune without explicit `--yes`.

## Recovery Path (if prune was accidental)

1. Restore deleted snapshots and index from VCS:
   - `git restore docs/autonomous-factory/archive/backlog-done-snapshot-*.md docs/autonomous-factory/archive/INDEX.md`
2. Rebuild archive index:
   - `uv run python scripts/backlog_archive_hygiene.py`
3. If snapshots are missing from VCS history, generate fresh snapshot from current backlog:
   - `uv run python scripts/backlog_archive_snapshot.py`
   - `uv run python scripts/backlog_archive_hygiene.py`

## Operator Routine

Daily/regular routine:

1. Validate backlog state:
   - `uv run python scripts/validate_backlog_markdown.py`
2. Check active focus summary:
   - `uv run python scripts/backlog_status.py`
3. Keep archive index fresh:
   - `uv run python scripts/backlog_archive_hygiene.py`

## Artifacts

- Archive directory: `docs/autonomous-factory/archive/`
- Index file: `docs/autonomous-factory/archive/INDEX.md`
- Snapshots: `backlog-done-snapshot-YYYYmmdd-HHMMSS.md`

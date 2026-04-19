# 19. Unclassified Delta Decision Register

Date: 2026-04-11

## Purpose

Machine-readable decision registry for paths in `other_unclassified` from upstream delta triage.

## Source of Truth

- JSON registry: `docs/ops/upstream-unclassified-decisions.json`
- Contract checker: `scripts/check_unclassified_delta_decisions.py`
- Markdown report: `docs/ops/upstream-unclassified-decisions.md`
- Report renderer/checker: `scripts/render_unclassified_decision_report.py`
- Preflight integration: `scripts/upstream_sync_preflight.sh`

## Current Snapshot

Current unclassified paths: `16`

- decision `already-absorbed`: `16`
- decision `defer`: `0`
- decision `merge-now`: `0`

## Operational Rule

Any new path that appears in `other_unclassified` must be added to the JSON registry with:

1. `decision` (`merge-now` | `defer` | `already-absorbed`)
2. `rationale` (short concrete reason)
3. `backlog_items` (non-empty list of task ids)
4. `validation` (non-empty list of commands)

Until covered, preflight must fail.
After JSON update, markdown report must be re-rendered and remain in sync.

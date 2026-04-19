# 15. Upstream Sync Governance

Date: 2026-04-10

## Goal

Define a repeatable, non-ad-hoc process for syncing Hive upstream into this local autonomous factory without breaking:

1. project-scoped sessions,
2. autonomous pipeline + ops controls,
3. telegram bridge operations,
4. container runtime parity.

## Sync Cadence

1. Security wave: weekly (or immediately on critical CVE/security fix).
2. Core stability wave: bi-weekly.
3. Optional tooling wave: monthly.
4. High-risk refactor wave: only by explicit backlog item and dedicated regression window.

## Mandatory Wave Order

1. `security-first` (P0 only).
2. `core-stability` (runtime crash/consistency fixes).
3. `optional tooling` (feature-flagged, disabled by default).
4. `high-risk refactors` (memory/session/runtime architecture changes).

No skipping or reordering in one merge batch.

## Pre-Flight Checklist (Before Any Upstream Merge)

1. Create/refresh backlog execution wave in `12-backlog-task-list.md`.
2. Set exactly one `in_progress` item and sync `Current Focus`.
3. Run:
   - `uv run python scripts/validate_backlog_markdown.py`
   - `uv run python scripts/backlog_status.py --path docs/autonomous-factory/12-backlog-task-list.md`
4. Capture upstream delta:
   - `git rev-list --left-right --count HEAD...origin/main`
   - `git diff --name-status HEAD..origin/main`
5. Mark conflict hotspots (`session_manager`, `routes_execution`, `workspace.tsx`, telegram bridge, project/autonomous APIs).
6. Preferred wrapper:
   - `./scripts/upstream_sync_preflight.sh [target_ref]`

## Merge Execution Rules

1. One backlog item = one bounded merge objective with explicit validation evidence.
2. Prefer file-level backport over blind branch sync for hotspot files.
3. Optional features must be guarded (default behavior unchanged).
4. Never mix high-risk architectural refactor with unrelated tooling additions.
5. For each merged item, add:
   - changed file set,
   - risk note,
   - validation commands + outputs.

## Do-Not-Break Local Factory Guardrails

1. Do not regress project boundary guarantees (`project_id` isolation).
2. Do not regress autonomous endpoints and loop orchestration contracts.
3. Do not regress telegram command/control behavior.
4. Do not regress docker runtime parity (`local code` vs `hive-core` container).
5. Do not remove local ops scripts/runbooks without equivalent replacement.

## Regression Gate (Required After Each Wave)

1. Targeted tests for touched domains.
2. `./scripts/acceptance_toolchain_self_check.sh`
3. `./scripts/check_runtime_parity.sh`
4. `uv run python scripts/check_backlog_status_consistency.py`
5. Update backlog status and keep only one active `in_progress` item.
6. Preferred wrapper:
   - `./scripts/upstream_sync_regression_gate.sh`

## Rollback Procedure

1. Revert only the affected backlog wave commits/files.
2. Re-run:
   - `./scripts/check_runtime_parity.sh`
   - `uv run --active pytest core/framework/server/tests/test_api.py -k "sessions or autonomous" -q`
   - `uv run --active pytest core/framework/server/tests/test_telegram_bridge.py -q`
3. Mark backlog item `blocked` with reason and recovery note.

## Evidence Storage

1. Keep validation evidence inside backlog item progress sections.
2. Keep operational artifacts in:
   - `docs/ops/backlog-status/`
   - `docs/ops/acceptance/`
3. Never close a wave item without commands and pass/fail result summary.

## Standard Wave Template

1. Audit upstream delta for the scoped files.
2. Apply minimal safe patch set.
3. Run lint/build/tests for touched components.
4. Run regression gate scripts.
5. Update backlog status (`done`) and promote next item (`in_progress`).
6. Re-validate backlog consistency scripts.

This template is mandatory for all future upstream integrations.

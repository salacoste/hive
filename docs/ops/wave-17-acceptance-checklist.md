# Wave 17 Acceptance Checklist (Tasks 571..576)

Date: 2026-05-03  
Scope: Runtime + Cross-Channel Consistency hardening wave.

## Task Coverage

1. `571` Cross-channel session binding contract
- [x] Bridge binding endpoint available: `GET /api/telegram/bridge/bindings`
- [x] Web-originated messages can rebind stale chat/session mapping deterministically
- [x] Test coverage present for bind/rebind transitions

2. `572` Message mirror + dedupe across interfaces
- [x] Web optimistic user message reconcile uses FIFO + unreconciled-only match
- [x] Shared helper used by queen DM and colony chat
- [x] Frontend tests cover duplicate-prevention contract

3. `573` Provider reliability policy
- [x] Heavy chain precedence: `claude-opus-4-6 -> gpt-5.4 -> openai/glm-5.1`
- [x] `/api/llm/queue/status` exposes queue + fallback attempt chains
- [x] Tests validate fallback telemetry and routing precedence

4. `574` Container-only runtime parity gate
- [x] `scripts/check_runtime_parity.sh` validates Web + bridge + llm status contracts
- [x] Container-safe Data behavior documented (`Session Data Explorer` / `.zip` path)
- [x] LLM contract checker passes in container-first mode

5. `575` GitHub PR review feedback integration gate
- [x] GitHub credential preflight before autonomous review/validation
- [x] Paginated ingestion for PR reviews/comments/issue comments
- [x] Pipeline report contains `review_feedback_summary` section

6. `576` Backlog and sprint re-activation
- [x] `_bmad-output` workflow/sprint artifacts aligned with active wave
- [x] Backlog status artifacts refreshed and indexed
- [x] Current focus synchronized to `in_progress=[576]`

## Verification Commands

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/validate_backlog_markdown.py
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_consistency.py
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status.py --json
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_artifact.py --output docs/ops/backlog-status/latest.json
./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_hygiene.py --keep 200
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_artifacts_index.py
```

## Exit Criteria

- Backlog parser reports one active task (`576`) and no drift.
- Wave-17 checklist remains reproducible in container-first run mode.
- Next step after closure: mark `576` as `done`, run retrospective summary, and open next wave.

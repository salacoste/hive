# Wave 15 — ND-2A Config-Only Replay Plan

Date: 2026-04-24
Status: executed (pending commit/sign-off)

## Scope

Replay candidate `ND-2A-config-only` (12 files):

- `examples/templates/competitive_intel_agent/mcp_servers.json`
- `examples/templates/deep_research_agent/mcp_servers.json`
- `examples/templates/email_inbox_management/mcp_servers.json`
- `examples/templates/email_reply_agent/mcp_servers.json`
- `examples/templates/job_hunter/mcp_servers.json`
- `examples/templates/local_business_extractor/mcp_servers.json`
- `examples/templates/meeting_scheduler/mcp_servers.json`
- `examples/templates/sdr_agent/mcp_servers.json`
- `examples/templates/tech_news_reporter/mcp_servers.json`
- `examples/templates/twitter_news_agent/mcp_servers.json`
- `examples/templates/vulnerability_assessment/mcp_registry.json`
- `examples/templates/vulnerability_assessment/mcp_servers.json`

## Preconditions

1. Keep Wave 14 guardrail policy unchanged (no destructive apply).
2. Ensure ND-2A probe is green:
   - `docs/ops/upstream-migration/wave15-nd2a-config-probe-2026-04-24.json`
   - `git_apply_check_exit_code=0`.

## Execution checklist

1. Preflight baseline:
   - `./scripts/upstream_sync_preflight.sh`
2. Apply bounded patch:
   - `git apply docs/ops/upstream-migration/wave15-nd2a-config-only.patch`
3. Run mandatory full gate:
   - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full ./scripts/upstream_sync_regression_gate.sh`
4. Inspect diff only for ND-2A scope:
   - `git diff --name-only -- examples/templates`
5. If gate passes, continue with normal commit flow.

## Rollback checklist

If regression gate fails before commit:

1. Revert only ND-2A files:
   - `git restore --worktree --staged -- <path>` (for each ND-2A file)
2. Re-run smoke gate to confirm clean state:
   - `./scripts/upstream_sync_regression_gate.sh`

## Evidence to attach after execution

- gate output (`smoke` + `full`) summary;
- resulting file list and patch scope confirmation;
- backlog status refresh (`scripts/backlog_status.py`).

## Execution result (2026-04-24)

Artifact:

- `docs/ops/upstream-migration/wave15-nd2a-execution-2026-04-24.json`

Outcome:

- patch applied successfully;
- changed files in scope: `12/12`;
- full regression gate passed:
  - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full ... upstream_sync_regression_gate.sh`
  - summary: `ok=7 failed=0`.

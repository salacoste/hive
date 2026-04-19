# Phase B Closure Checklist (Autonomous Pipeline Determinism)

Source of truth: `docs/autonomous-factory/13-master-implementation-plan.md` -> `Phase B`.

## Exit Criteria

1. Stage transitions and retry/escalation behavior are deterministic.
2. Terminal run outcomes are reproducible via server-driven orchestration.
3. PR-ready report shape is stable and produced for terminal runs.

## Command Checklist

```bash
# 1) full autonomous pipeline API suite
uv run pytest core/framework/server/tests/test_api.py -k "pipeline_" -q

# 2) focused deterministic scenarios
uv run pytest core/framework/server/tests/test_api.py -k "escalates_on_review_after_retries or evaluate_endpoint_uses_checks_and_updates_report or run_until_terminal_endpoint or execute_next_endpoint or run_cycle_reports_terminal_and_pr_ready" -q

# 3) runtime contract parity
./scripts/check_runtime_parity.sh

# 4) acceptance self-check (backlog/guardrails/docs/toolchain)
./scripts/acceptance_toolchain_self_check.sh
```

## Latest Closure Evidence

Date: `2026-04-10` (local run)

- `pipeline_` API tests: `27 passed, 106 deselected`.
- deterministic subset tests: `5 passed, 128 deselected`.
- `check_runtime_parity.sh`: `runtime parity check passed`.
- `acceptance_toolchain_self_check.sh`: `ok=19 failed=0`.

## Notes

- Determinism is verified at API level for:
  - retry -> `retry_pending`,
  - escalation after retry limit,
  - run-until-terminal / execute-next bounded orchestration,
  - report and checks-driven evaluation flow.

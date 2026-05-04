# Wave 14 — Selective Deferred-Lane Adoption Plan

Date: 2026-04-24
Status: closure-ready (destructive apply blocked)

## Objective

Define a bounded, reversible path to adopt only explicitly approved pieces from
deferred destructive upstream lanes, while preserving local autonomous-factory
operational contracts.

## Guardrail baseline

Protected destructive deletes on `HEAD..upstream/main`:

- `scripts`: `164`
- `.github/workflows`: `3`
- `docs/autonomous-factory`: `34`
- `docs/ops`: `57`
- `ai-proxy-docs`: `5`
- total protected flagged: `263`

Evidence command:

```bash
./scripts/hive_ops_run.sh uv run --no-project python scripts/check_upstream_destructive_lanes.py \
  --base-ref HEAD --upstream-ref upstream/main --json
```

Dry-run matrix artifact:

- `docs/ops/upstream-migration/wave14-allowlist-probe-2026-04-24.json`
- rerun after finalized lane decisions:
  - `docs/ops/upstream-migration/wave14-allowlist-probe-r2-2026-04-24.json`

Scenario results (current):

1. `strict` (no allowlist): `flagged_total=263`
2. `archives_migration_only`:
   - allowlist:
     - `docs/autonomous-factory/archive/`
     - `docs/ops/upstream-migration/`
   - result: `flagged_total=223`
3. `generated_ops_artifacts`:
   - allowlist:
     - `docs/autonomous-factory/archive/`
     - `docs/ops/upstream-migration/`
     - `docs/ops/acceptance-reports/`
     - `docs/ops/backlog-status/`
     - `docs/ops/google-canary/`
     - `docs/ops/telegram-signoff/`
   - result: `flagged_total=218`

Scenario results (rerun `r2`, with finalized lane decisions):

1. `strict` -> `flagged_total=263`
2. `archives_migration_only` -> `223`
3. `generated_ops_artifacts` -> `218`

`r2` blocker distribution (`generated_ops_artifacts`):

- `scripts`: `164`
- `.github/workflows`: `3`
- `docs/autonomous-factory`: `31`
- `docs/ops`: `15`
- `ai-proxy-docs`: `5`

Conclusion:

- Even expanded low-risk docs allowlist keeps a large protected destructive
  delta (`218`) unresolved, so destructive apply remains blocked (confirmed by `r2` rerun).
- Remaining blockers in the widest tested low-risk scenario (`218`):
  - `scripts/**`: `164`
  - `.github/workflows/**`: `3`
  - `docs/autonomous-factory/**`: `31`
  - `docs/ops/**`: `15`
  - `ai-proxy-docs/**`: `5`

Granular review table reference:

- `docs/ops/upstream-migration/wave14-granular-lane-review-2026-04-24.md`

## Adoption protocol (required)

1. Create explicit allowlist prefixes for the target sub-lane only.
2. Run destructive-lane checker in dry-run mode with that allowlist.
3. Attach JSON report to migration evidence docs.
4. Apply only the approved subset.
5. Run mandatory regression gate:
   - framework server API + telegram tests,
   - frontend tests + build,
   - container/runtime smoke.
6. Update backlog + decision log before moving to next sub-lane.

## Post-apply regression gate matrix (codified)

Canonical gate entrypoint:

- `scripts/upstream_sync_regression_gate.sh`

Profiles:

1. `smoke` (default)
   - acceptance toolchain self-check;
   - runtime parity;
   - backlog consistency.
2. `full`
   - everything from `smoke`;
   - server API pytest bundle;
   - Telegram bridge pytest bundle;
   - frontend unit tests;
   - frontend build.

Execution examples:

```bash
# smoke matrix (required for every bounded apply)
./scripts/upstream_sync_regression_gate.sh

# full matrix (required before lane sign-off)
HIVE_UPSTREAM_SYNC_GATE_PROFILE=full \
HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default \
./scripts/upstream_sync_regression_gate.sh
```

Container-first behavior:

- when Docker CLI is available, the gate runs commands via `hive-ops`
  (`scripts/hive_ops_run.sh`) to keep checks reproducible across machines;
- host fallback is preserved when Docker is unavailable.

## Candidate sequence (bounded)

1. Docs archive-only cleanup
   - potential allowlist candidates:
     - `docs/autonomous-factory/archive/`
     - `docs/ops/upstream-migration/`
   - expected result: reduce protected flagged count without touching active
     runbooks/contracts.
   - probe result (dry-run):
     - with both allowlist prefixes, protected flagged count drops
       from `263` to `223` (still blocked, as expected).
2. Workflow lane review (`.github/workflows/**`)
   - compare each deleted workflow against current local CI/ops needs.
3. Scripts lane review (`scripts/**`)
   - only with per-script decision table and replacement mapping.

## Explicit no-adopt (current)

1. `scripts/browser_remote_ui.html` upstream modification
   - references `browser_activate_tab`, but local tool surface still uses
     `browser_focus`.
2. `scripts/check_llm_key.py` upstream modification
   - drops local proxy validation branches needed for current deployment
     (`gemini proxy`, `anthropic`/`clove` compatible endpoint checks).

## Wave 14 closure-ready state

- guardrail + dry-run matrix + lane decisions are complete for this wave;
- destructive apply remains blocked by design until explicit owner allowlist;
- next wave should focus on non-destructive upstream lanes (`M/A/R`) with
  bounded replay batches.
- handoff target:
  - `docs/ops/upstream-migration/wave15-non-destructive-plan-2026-04-24.md`

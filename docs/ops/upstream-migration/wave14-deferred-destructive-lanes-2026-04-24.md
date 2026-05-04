# Wave 14 — Deferred Destructive Lanes (Guarded)

Date: 2026-04-24

## Goal

Prepare safe migration basis for previously deferred destructive upstream lanes
without applying mass deletions to local autonomous-factory operational assets.

## Snapshot (`HEAD..upstream/main`)

- branch drift: `ahead=8`, `behind=53`
- scripts/workflows delta profile:
  - mostly `D` (mass deletions under `.github/workflows/**` and `scripts/**`)
  - only two `M` entries:
    - `scripts/browser_remote_ui.html`
    - `scripts/check_llm_key.py`

## Safety decision (this wave)

1. Keep destructive upstream deletions deferred for:
   - `.github/workflows/**`
   - `scripts/**`
   - `docs/autonomous-factory/**`
   - `docs/ops/**`
   - `ai-proxy-docs/**`
2. Do **not** adopt `scripts/browser_remote_ui.html` upstream change now:
   - upstream replaces `browser_focus` with `browser_activate_tab`;
   - current codebase/tools still expose `browser_focus`, not `browser_activate_tab`.
3. Do **not** adopt `scripts/check_llm_key.py` upstream change now:
   - upstream removes local proxy-specific Anthropic-compatible checks
     (`anthropic`/`clove`) and custom Gemini proxy branch;
   - current local deployment relies on these provider/proxy checks.

## Implemented guardrail

Added gate script:

- `scripts/check_upstream_destructive_lanes.py`
  - parses `git diff --name-status <base>..<upstream>`
  - fails on protected `D` entries unless explicitly allowlisted by prefix
  - supports human and JSON output

Added tests:

- `scripts/tests/test_check_upstream_destructive_lanes.py`

Validation:

1. `./scripts/hive_ops_run.sh uv run pytest scripts/tests/test_check_upstream_destructive_lanes.py -q`
   - `5 passed`
2. `./scripts/hive_ops_run.sh uv run python scripts/check_upstream_destructive_lanes.py --base-ref HEAD --upstream-ref upstream/main`
   - `fail` (expected): protected destructive deletes detected (`flagged_total=263`)

## Next bounded step

Before any destructive lane adoption, require:

1. explicit allowlist prefixes for intended deletions,
2. dry-run report archive attached to backlog item,
3. post-apply regression gate (server + frontend + container smoke).

Current dry-run allowlist probe:

- `docs/ops/upstream-migration/wave14-allowlist-probe-2026-04-24.json`

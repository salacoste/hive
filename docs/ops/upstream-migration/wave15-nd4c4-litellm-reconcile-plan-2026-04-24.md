# Wave 15 — ND-4C4 litellm.py Reconcile Plan

Date: 2026-04-24
Status: in progress

## File

- `core/framework/llm/litellm.py`

## Current delta shape (local vs upstream)

- diffstat: `615 insertions`, `787 deletions` (`1402` changed lines).
- high-risk zones (must preserve local behavior):
  - provider routing and proxy base handling;
  - rate-limit queueing/semaphore behavior;
  - Claude OAuth patch + retry/failover behavior;
  - OpenRouter/Gemini/GLM compatibility branches;
  - system-prompt cache-control / dynamic suffix handling.

## Reconcile strategy

1. Keep local runtime guardrails as baseline.
2. Cherry-pick compatible upstream changes in narrow chunks:
   - import/type cleanups;
   - helper normalization (`_get_env_int`, base-url helper functions) where non-breaking;
   - logging/defensive wrappers with zero behavior drift.
3. Avoid destructive change of routing/fallback contracts until dedicated validation is green.
4. Treat `core/framework/llm/fallback.py` deletion as separate deferred destructive lane.

## Validation matrix

- targeted tests:
  - `uv run pytest core/tests/test_litellm_provider.py core/tests/test_litellm_streaming.py core/tests/test_queen_nodes_prompt.py core/tests/test_queen_memory.py core/tests/test_trigger_fires_into_queen.py -q`
- mandatory gate:
  - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`

## Exit criteria

- `litellm.py` reconciled with documented accepted upstream chunks;
- no regression in queue/fallback/proxy behavior;
- targeted tests + full gate green;
- ND-4C4 execution artifact published.

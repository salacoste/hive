# Wave 15 — ND-4C Framework Skills + Queen/LLM Wiring Triage

Date: 2026-04-24
Status: triage complete, ND-4C1..ND-4C4 executed

## Source artifact

- `docs/ops/upstream-migration/wave15-nd4c-framework-triage-2026-04-24.json`

## Scope snapshot (`HEAD..upstream/main`)

- bounded prefixes:
  - `core/framework/skills`
  - `core/framework/agents/queen`
  - `core/framework/llm`
  - `core/framework/loader`
  - `core/framework/host`
- totals:
  - files total: `34`
  - non-destructive: `33`
  - destructive: `1` (`core/framework/llm/fallback.py`, deferred)

## Lane split

1. ND-4C1 `framework skills surface` (executed)
   - scope: `core/framework/skills/*` non-destructive delta (`10` files).
2. ND-4C2 `queen/llm/loader/host wiring` (executed)
   - scope: remaining non-destructive files under selected prefixes, excluding destructive lanes.
3. ND-4C3 `queen + llm wiring`
   - scope: residual non-destructive files in `core/framework/agents/queen` and `core/framework/llm`.

## ND-4C1 execution result

- artifacts:
  - `docs/ops/upstream-migration/wave15-nd4c1-framework-skills.patch`
  - `docs/ops/upstream-migration/wave15-nd4c1-framework-skills-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd4c1-framework-skills-replay-plan-2026-04-24.md`
  - `docs/ops/upstream-migration/wave15-nd4c1-framework-skills-execution-2026-04-24.json`
- probe status: `git apply --check` pass (`exit_code=0`).
- validation:
  - skills-targeted tests: `256 passed`;
  - full regression gate: `ok=7 failed=0`.

## ND-4C2 execution result

- selected first ND-4C2 bounded candidate:
  - `loader + host` sub-scope (`8` files).
- artifacts:
  - `docs/ops/upstream-migration/wave15-nd4c2-loader-host.patch`
  - `docs/ops/upstream-migration/wave15-nd4c2-loader-host-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd4c2-loader-host-replay-plan-2026-04-24.md`
  - `docs/ops/upstream-migration/wave15-nd4c2-loader-host-execution-2026-04-24.json`
- probe status:
  - `git apply --check` pass (`exit_code=0`).
- validation:
  - targeted framework/runtime suite: `415 passed, 9 skipped`;
  - full regression gate: `ok=7 failed=0`.

## ND-4C3 planning status

- selected bounded candidate:
  - `queen + llm` sub-scope (`15` files, non-destructive only).
- artifacts:
  - `docs/ops/upstream-migration/wave15-nd4c3-queen-llm.patch`
  - `docs/ops/upstream-migration/wave15-nd4c3-queen-llm-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd4c3-queen-llm-replay-plan-2026-04-24.md`
- probe status:
  - `git apply --check` failed (`exit_code=1`) on:
    - `core/framework/agents/queen/nodes/__init__.py`
    - `core/framework/llm/litellm.py`
- classification:
  - `reconcile-required`.

## Next lane

- `ND-4C3` queen + llm bounded replay execution.

## ND-4C3 execution result

- execution mode:
  - reconcile-mode with partial apply + deferred conflicts.
- applied upstream subset:
  - `13/15` files from queen+llm scope.
- deferred conflicts:
  - `core/framework/agents/queen/nodes/__init__.py`
  - `core/framework/llm/litellm.py`
- evidence:
  - `docs/ops/upstream-migration/wave15-nd4c3-queen-llm-execution-2026-04-24.json`
- validation:
  - targeted checks: `145 passed, 9 skipped`;
  - full regression gate: `ok=7 failed=0`.

## Next lane

- `ND-4C4` reconcile blocked `queen/nodes` + `llm/litellm`.

## ND-4C4 progress

- resolved:
  - `core/framework/agents/queen/nodes/__init__.py` (upstream direct sync).
- evidence:
  - `docs/ops/upstream-migration/wave15-nd4c4-reconcile-progress-2026-04-24.json`
- litellm reconcile playbook:
  - `docs/ops/upstream-migration/wave15-nd4c4-litellm-reconcile-plan-2026-04-24.md`
- targeted checks:
  - `145 passed, 9 skipped`.
- full gate:
  - `ok=7 failed=0`.
- execution evidence:
  - `docs/ops/upstream-migration/wave15-nd4c4-reconcile-execution-2026-04-24.json`
- remaining divergence:
  - `core/framework/llm/litellm.py` preserved as intentional local divergence
    (proxy/runtime guardrails), with duplicate `json_object` hint branch removed.

## Next lane

- post-ND4 residual inventory refresh and next bounded candidate selection.

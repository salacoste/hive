# Wave 15 — ND-4 Core (Frontend + Framework) Triage

Date: 2026-04-24
Status: ND-4 triage complete, ND-4A/ND-4B/ND-4C1 executed

## Source artifact

- `docs/ops/upstream-migration/wave15-nd4-core-inventory-2026-04-24.json`

## Scope snapshot (`HEAD..upstream/main`)

- scoped paths:
  - `core/frontend`
  - `core/framework`
- totals:
  - all changed files: `173`
  - non-destructive (`M/A/R100`): `101`
  - destructive (`D`): `77`
- non-destructive split:
  - `core/frontend`: `31`
  - `core/framework`: `70`

## Risk profile

1. Destructive footprint is high (`77` deletes), mostly:
   - `core/framework/graph`: `29` files;
   - `core/framework/runtime`: `21` files;
   - `core/framework/server`: `14` files;
   - `core/framework/runner`: `11` files.
2. For current wave, destructive lanes remain deferred by policy.
3. Immediate work is limited to bounded non-destructive candidates only.

## Lane split (bounded)

1. ND-4A `frontend tools surface` (first replay candidate)
   - focus: additive UI/API surface for tools management and library pages.
   - artifact set:
     - `docs/ops/upstream-migration/wave15-nd4a-frontend-tools.patch`
     - `docs/ops/upstream-migration/wave15-nd4a-frontend-tools-probe-2026-04-24.json`
     - `docs/ops/upstream-migration/wave15-nd4a-frontend-tools-replay-plan-2026-04-24.md`
2. ND-4B `frontend conversation/runtime UX` (executed)
   - focus: chat/session integration deltas (`chat-helpers`, `colony-chat`, `queen-dm`, `execution/sessions` APIs).
3. ND-4C `framework skills + queen/llm wiring` (deferred)
   - focus: `core/framework/skills/*`, selective `agents/*`, `llm/*`, `loader/*`, `host/*`.
4. ND-4D `framework runtime/server restructuring` (deferred, destructive-adjacent)
   - includes server and runtime areas with high coupling to deferred deletions.

## ND-4A execution result

- probe:
  - `git apply --check` passed (`exit_code=0`) for ND-4A bounded patch.
- replay executed with bounded reconcile follow-ups for dependent typings/API.
- validation:
  - frontend tests: `49 passed`;
  - frontend build: `ok`;
  - full regression gate: `ok=7 failed=0`.
- evidence:
  - `docs/ops/upstream-migration/wave15-nd4a-frontend-tools-execution-2026-04-24.json`.

## ND-4B execution result

- probe:
  - bounded `git apply --check` failed on `4` files; reconcile mode selected.
- replay executed with mixed reconcile strategy:
  - direct upstream sync: `6` files;
  - clean three-way merge: `2` files;
  - manual conflict resolution: `4` files.
- validation:
  - frontend tests: `53 passed`;
  - frontend build: `ok`;
  - full regression gate: `ok=7 failed=0`.
- evidence:
  - `docs/ops/upstream-migration/wave15-nd4b-frontend-runtime-execution-2026-04-24.json`.

## ND-4C1 execution result

- triage scope narrowed to framework prefixes:
  - `skills`, `agents/queen`, `llm`, `loader`, `host`.
- first bounded candidate executed:
  - `ND-4C1` framework skills surface (`10` files).
- validation:
  - skills-targeted tests: `256 passed`;
  - full regression gate: `ok=7 failed=0`.
- evidence:
  - `docs/ops/upstream-migration/wave15-nd4c1-framework-skills-execution-2026-04-24.json`.

## Next lane

- `ND-4C2` queen/llm/loader/host bounded replay plan.

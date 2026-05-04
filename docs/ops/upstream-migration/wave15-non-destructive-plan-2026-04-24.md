# Wave 15 — Non-Destructive Upstream Adoption Plan

Date: 2026-04-24
Status: in progress

## Objective

Start a bounded adoption wave for non-destructive upstream delta
(`M`/`A`/`R100`) after Wave 14 destructive-lane hardening.

## Source inventory

Artifact:

- `docs/ops/upstream-migration/wave15-non-destructive-inventory-2026-04-24.json`

Current non-destructive delta (`HEAD..upstream/main`):

- `M=124`
- `A=39`
- `R100=3`
- total=`166`

Top prefixes (by file count):

- `core/framework`: `65`
- `core/frontend`: `31`
- `tools`: `27`
- `core`: `18`
- `examples`: `15`
- `(root)`: `3`
- `docs`: `3`
- `scripts`: `2`

## Bounded sequence (proposed)

1. ND-1 `docs` lane
   - files:
     - `docs/skill-registry-prd.md` (`M`)
     - `docs/releases/v0.10.3.md` (`A`)
     - `docs/releases/v0.10.4.md` (`A`)
   - goal: low-risk doc alignment and release-note adoption.
2. ND-2 `examples/templates` lane
   - mostly `mcp_servers.json` and template wiring updates.
3. ND-3 `tools` lane (selected sub-batches only).
4. ND-4 `core/frontend` and `core/framework` only by focused bounded batches.

## Explicit constraints inherited from Wave 14

1. No destructive apply without explicit owner allowlist.
2. Keep no-adopt decisions for:
   - `scripts/browser_remote_ui.html` (`browser_activate_tab` mismatch);
   - `scripts/check_llm_key.py` (local proxy checks must be preserved).
3. Any bounded apply must pass:
   - preflight guardrails;
   - post-apply full regression gate.

## First actionable batch candidate

`ND-1 docs lane` only, as isolated replay candidate with mandatory gates.

## ND-1 probe (current)

Artifacts:

- `docs/ops/upstream-migration/wave15-nd1-docs-probe-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd1-docs.patch`

Probe result:

- `git apply --check` on full ND-1 patch failed:
  - `docs/releases/v0.10.3.md: already exists in working directory`
- implication:
  - ND-1 should use per-file merge/reconcile flow (not blind patch apply),
    because local workspace already contains release docs overlapping upstream `A` paths.

Next bounded step:

1. Build per-file reconcile table for the 3 ND-1 files (`ours vs upstream`).
2. Replay ND-1 as explicit file-level updates.
3. Run full regression gate after replay.

## ND-1 reconcile result

Artifact:

- `docs/ops/upstream-migration/wave15-nd1-docs-reconcile-2026-04-24.json`

Result:

- all 3 ND-1 files are already byte-equal to `upstream/main` in current
  worktree (`all_files_content_equal_to_upstream=true`).

Decision:

- skip patch replay for ND-1 and carry these files via normal commit flow;
- move active adoption analysis to `ND-2 examples/templates lane`.

## ND-2 lane triage (active)

Artifacts:

- `docs/ops/upstream-migration/wave15-nd2-examples-inventory-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd2-examples-triage-2026-04-24.md`

Current split:

- total ND-2 files: `15`
- config-only low-risk: `12`
- code-bearing medium-risk: `3`

Selected first bounded replay candidate:

- `ND-2A-config-only` (12 config files).
- execution checklist:
  - `docs/ops/upstream-migration/wave15-nd2a-config-replay-plan-2026-04-24.md`

ND-2A technical probe:

- `git apply --check` passed (`docs/ops/upstream-migration/wave15-nd2a-config-probe-2026-04-24.json`).
- status: ready-for-replay with mandatory post-apply full gate.

ND-2A execution result:

- executed with full gate pass (`ok=7 failed=0`);
- evidence:
  - `docs/ops/upstream-migration/wave15-nd2a-execution-2026-04-24.json`;

ND-2B execution result:

- executed with full gate pass (`ok=7 failed=0`);
- evidence:
  - `docs/ops/upstream-migration/wave15-nd2b-execution-2026-04-24.json`;
- ND-2 lane status:
  - completed (`15/15` files bounded replayed via ND-2A + ND-2B).

## ND-3 lane triage (active)

Artifacts:

- `docs/ops/upstream-migration/wave15-nd3-tools-inventory-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3-tools-triage-2026-04-24.md`
- `docs/ops/upstream-migration/wave15-nd3a-prometheus.patch`
- `docs/ops/upstream-migration/wave15-nd3a-prometheus-probe-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3a-prometheus-replay-plan-2026-04-24.md`
- `docs/ops/upstream-migration/wave15-nd3a-prometheus-reconcile-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3a-execution-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3b-gcu.patch`
- `docs/ops/upstream-migration/wave15-nd3b-gcu-probe-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3b-gcu-replay-plan-2026-04-24.md`
- `docs/ops/upstream-migration/wave15-nd3b-execution-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3c-productivity.patch`
- `docs/ops/upstream-migration/wave15-nd3c-productivity-probe-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3c-productivity-replay-plan-2026-04-24.md`
- `docs/ops/upstream-migration/wave15-nd3c-execution-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3d-runtime.patch`
- `docs/ops/upstream-migration/wave15-nd3d-runtime-probe-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3d-runtime-replay-plan-2026-04-24.md`
- `docs/ops/upstream-migration/wave15-nd3d-runtime-reconcile-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3d-execution-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3e-deletions-probe-2026-04-24.json`
- `docs/ops/upstream-migration/wave15-nd3e-deletions-plan-2026-04-24.md`
- `docs/ops/upstream-migration/wave15-nd3e-execution-2026-04-24.json`

Current ND-3 snapshot (`tools` prefix, `HEAD..upstream/main`):

- total files: `29` (`M=22`, `A=5`, `D=2`);
- byte-equal to upstream: `3`;
- divergent vs upstream: `22`;
- local missing while upstream adds: `2`.

Selected first bounded candidate:

- `ND-3A` Prometheus observability sub-lane (`8` files).

ND-3A probe result:

- `git apply --check` failed (`exit_code=1`);
- reasons: pre-existing local files plus divergent hunks in `health_check.py`,
  `tools/__init__.py`, and `test_health_checks.py`.

ND-3A execution result:

- executed in reconcile mode with full gate pass (`ok=7 failed=0`);
- evidence:
  - `docs/ops/upstream-migration/wave15-nd3a-execution-2026-04-24.json`;
- post-reconcile classifications:
  - `aligned_to_upstream=6`,
  - `intentional_local_divergence=2`.

ND-3B execution result:

- executed with full gate pass (`ok=7 failed=0`);
- evidence:
  - `docs/ops/upstream-migration/wave15-nd3b-execution-2026-04-24.json`.

ND-3C execution result:

- executed with full gate pass (`ok=7 failed=0`);
- evidence:
  - `docs/ops/upstream-migration/wave15-nd3c-execution-2026-04-24.json`.

Next active sub-lane:

- `ND-3D` runtime packaging (`4` files), reconcile-required
  (`coder_tools_server.py` hunk mismatch in probe).

ND-3D execution result:

- executed in reconcile mode with full gate pass (`ok=7 failed=0`);
- evidence:
  - `docs/ops/upstream-migration/wave15-nd3d-execution-2026-04-24.json`;
- note:
  - runtime packaging lane completed with intentional local divergence
    preserved where required by local deployment model.

ND-3E execution result:

- upstream-deleted legacy files removed locally:
  - `tools/src/aden_tools/tools/google_auth.py`
  - `tools/tests/tools/test_google_auth.py`
- no remaining references detected in `tools/src` and `tools/tests`;
- full gate passed (`ok=7 failed=0`);
- evidence:
  - `docs/ops/upstream-migration/wave15-nd3e-execution-2026-04-24.json`.

Next active lane:

- `ND-4` core/frontend + core/framework bounded triage and candidate replay plan.

ND-4 triage result:

- triage artifacts:
  - `docs/ops/upstream-migration/wave15-nd4-core-inventory-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd4-core-triage-2026-04-24.md`
- scope snapshot:
  - non-destructive files in `core/frontend+core/framework`: `101`;
  - destructive files (deferred by policy): `77`.
- first bounded candidate (`ND-4A`) prepared:
  - `docs/ops/upstream-migration/wave15-nd4a-frontend-tools.patch`
  - `docs/ops/upstream-migration/wave15-nd4a-frontend-tools-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd4a-frontend-tools-replay-plan-2026-04-24.md`
  - probe status: `git apply --check` pass (`exit_code=0`).

ND-4A execution result:

- replay executed with bounded reconcile follow-ups for dependency typings/API wiring;
- validation:
  - frontend tests: `49 passed`;
  - frontend build: `ok`;
  - full gate: `ok=7 failed=0`.
- evidence:
  - `docs/ops/upstream-migration/wave15-nd4a-frontend-tools-execution-2026-04-24.json`.

Next active sub-lane:

- `ND-4B` frontend conversation/runtime UX bounded replay.

ND-4B preparation status:

- artifacts:
  - `docs/ops/upstream-migration/wave15-nd4b-frontend-runtime.patch`
  - `docs/ops/upstream-migration/wave15-nd4b-frontend-runtime-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd4b-frontend-runtime-replay-plan-2026-04-24.md`
- probe result:
  - `git apply --check` failed (`exit_code=1`) on
    `api/execution.ts`, `lib/chat-helpers(.test).ts`, `pages/queen-dm.tsx`.
- decision:
  - ND-4B execution will proceed via reconcile mode.

ND-4B execution result:

- completed in reconcile mode with mixed strategy:
  - upstream direct sync: `6` files;
  - clean three-way merge: `2` files;
  - manual conflict resolution: `4` files.
- validation:
  - frontend tests: `53 passed`;
  - frontend build: `ok`;
  - full gate: `ok=7 failed=0`.
- evidence:
  - `docs/ops/upstream-migration/wave15-nd4b-frontend-runtime-execution-2026-04-24.json`.

Next active sub-lane:

- `ND-4C` core/framework skills + queen/llm wiring bounded triage.

ND-4C triage result:

- triage artifacts:
  - `docs/ops/upstream-migration/wave15-nd4c-framework-triage-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd4c-framework-triage-2026-04-24.md`
- bounded prefixes in scope:
  - `core/framework/skills`
  - `core/framework/agents/queen`
  - `core/framework/llm`
  - `core/framework/loader`
  - `core/framework/host`
- first bounded candidate selected:
  - `ND-4C1` framework skills surface (`10` files).

ND-4C1 execution result:

- artifacts:
  - `docs/ops/upstream-migration/wave15-nd4c1-framework-skills.patch`
  - `docs/ops/upstream-migration/wave15-nd4c1-framework-skills-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd4c1-framework-skills-replay-plan-2026-04-24.md`
  - `docs/ops/upstream-migration/wave15-nd4c1-framework-skills-execution-2026-04-24.json`
- probe status: `git apply --check` pass (`exit_code=0`);
- validation:
  - skills targeted tests: `256 passed`;
  - full regression gate: `ok=7 failed=0`.

Next active sub-lane:

- `ND-4C2` queen/llm/loader/host bounded replay.

ND-4C2 execution result:

- selected bounded candidate:
  - `loader + host` sub-scope (`8` files).
- artifacts:
  - `docs/ops/upstream-migration/wave15-nd4c2-loader-host.patch`
  - `docs/ops/upstream-migration/wave15-nd4c2-loader-host-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd4c2-loader-host-replay-plan-2026-04-24.md`
  - `docs/ops/upstream-migration/wave15-nd4c2-loader-host-execution-2026-04-24.json`
- probe status:
  - `git apply --check` pass (`exit_code=0`).
- validation:
  - targeted framework/runtime tests: `415 passed, 9 skipped`;
  - full regression gate: `ok=7 failed=0`.

Next active sub-lane:

- `ND-4C3` queen + llm bounded replay planning.

ND-4C3 planning status:

- selected bounded candidate:
  - `queen + llm` sub-scope (`15` files, non-destructive only).
- artifacts:
  - `docs/ops/upstream-migration/wave15-nd4c3-queen-llm.patch`
  - `docs/ops/upstream-migration/wave15-nd4c3-queen-llm-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd4c3-queen-llm-replay-plan-2026-04-24.md`
- probe status:
  - `git apply --check` failed (`exit_code=1`) on
    `core/framework/agents/queen/nodes/__init__.py` and
    `core/framework/llm/litellm.py`.
- classification:
  - `reconcile-required` for execution lane.

Next active sub-lane:

- `ND-4C3` queen + llm bounded replay execution.

ND-4C3 execution result:

- execution mode:
  - reconcile-mode with partial apply and deferred conflicts.
- applied upstream files:
  - `13/15` files from scoped queen+llm lane.
- deferred reconcile files:
  - `core/framework/agents/queen/nodes/__init__.py`
  - `core/framework/llm/litellm.py`
- evidence:
  - `docs/ops/upstream-migration/wave15-nd4c3-queen-llm-execution-2026-04-24.json`
- validation:
  - targeted checks: `145 passed, 9 skipped`;
  - full regression gate: `ok=7 failed=0`.

Next active sub-lane:

- `ND-4C4` reconcile blocked `queen/nodes` + `llm/litellm` files.

ND-4C4 progress:

- `core/framework/agents/queen/nodes/__init__.py` reconciled via upstream direct sync.
- progress evidence:
  - `docs/ops/upstream-migration/wave15-nd4c4-reconcile-progress-2026-04-24.json`
- litellm reconcile playbook:
  - `docs/ops/upstream-migration/wave15-nd4c4-litellm-reconcile-plan-2026-04-24.md`
- targeted ND-4C4 checks:
  - `145 passed, 9 skipped`.
- full gate:
  - `ok=7 failed=0`.
- execution evidence:
  - `docs/ops/upstream-migration/wave15-nd4c4-reconcile-execution-2026-04-24.json`
- `core/framework/llm/litellm.py` reconciliation outcome:
  - manual reconcile with intentional local divergence (proxy/runtime guardrails preserved),
    plus duplicate `json_object` hint branch cleanup.

Post-ND4 residual refresh result:

- snapshot artifact:
  - `docs/ops/upstream-migration/wave15-post-nd4-residual-inventory-2026-04-24.json`
- residual non-destructive total:
  - `174` files (`HEAD..upstream/main`).
- selected next bounded candidate:
  - `ND-5A` orchestrator micro-lane (`4` files):
    - `core/framework/orchestrator/client_io.py`
    - `core/framework/orchestrator/gcu.py`
    - `core/framework/orchestrator/node.py`
    - `core/framework/orchestrator/safe_eval.py`
- planning/probe artifacts:
  - `docs/ops/upstream-migration/wave15-nd5a-orchestrator.patch`
  - `docs/ops/upstream-migration/wave15-nd5a-orchestrator-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd5a-orchestrator-replay-plan-2026-04-24.md`
- probe status:
  - `git apply --check` pass (`exit_code=0`).

ND-5A execution result:

- replay applied from:
  - `docs/ops/upstream-migration/wave15-nd5a-orchestrator.patch`
- compatibility reconcile added:
  - `core/framework/host/event_bus.py` (`emit_client_input_requested` backward-compatible `prompt/options` path)
- targeted checks:
  - `uv run pytest core/tests/test_event_loop_node.py core/tests/test_safe_eval.py core/tests/test_node_conversation.py -q`
    -> `285 passed, 4 skipped`
- full regression gate:
  - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
    -> `ok=7 failed=0`
- execution artifact:
  - `docs/ops/upstream-migration/wave15-nd5a-orchestrator-execution-2026-04-24.json`

Post-ND5A residual refresh:

- snapshot artifact:
  - `docs/ops/upstream-migration/wave15-post-nd5a-residual-inventory-2026-04-24.json`

Next active sub-lane:

- `ND-5B` server mini-lane reconcile planning/probe:
  - `core/framework/server/README.md`
  - `core/framework/server/routes_events.py`
- artifacts:
  - `docs/ops/upstream-migration/wave15-nd5b-server-mini.patch`
  - `docs/ops/upstream-migration/wave15-nd5b-server-mini-probe-2026-04-24.json`
  - `docs/ops/upstream-migration/wave15-nd5b-server-mini-replay-plan-2026-04-24.md`
  - `docs/ops/upstream-migration/wave15-nd5b-server-mini-reconcile-analysis-2026-04-24.md`
  - `docs/ops/upstream-migration/wave15-nd5b-server-mini-progress-2026-04-24.json`
- probe status:
  - `git apply --check` -> `reconcile_required`.
- baseline validations:
  - `uv run --package framework pytest core/framework/server/tests/test_api.py -k "events or health" -q`
    -> `8 passed, 185 deselected`
  - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
    -> `ok=7 failed=0`

ND-5B execution result:

- reconcile decisions:
  - keep local `README` AppKey docs (`request.app[APP_KEY_MANAGER]`);
  - adopt upstream replay behavior for `routes_events.py` by restoring
    `EventType.TRIGGER_FIRED.value` inside `_REPLAY_TYPES`.
- execution artifact:
  - `docs/ops/upstream-migration/wave15-nd5b-server-mini-execution-2026-04-25.json`
- validation:
  - targeted server checks: `8 passed, 185 deselected`;
  - full regression gate: `ok=7 failed=0`.

Next active sub-lane:

- `ND-5C` agent-loop prompting micro-lane execution:
  - `core/framework/agent_loop/prompting.py`
- artifacts:
  - `docs/ops/upstream-migration/wave15-nd5c-agentloop-prompting.patch`
  - `docs/ops/upstream-migration/wave15-nd5c-agentloop-prompting-probe-2026-04-25.json`
  - `docs/ops/upstream-migration/wave15-nd5c-agentloop-prompting-replay-plan-2026-04-25.md`
  - `docs/ops/upstream-migration/wave15-nd5c-agentloop-prompting-execution-2026-04-25.json`
- validation (current):
  - targeted checks:
    - `uv run pytest core/tests/test_event_loop_node.py core/tests/test_node_conversation.py -q`
      -> `163 passed, 4 skipped`
  - full regression gate:
    - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
    -> `ok=7 failed=0`

ND-5C execution result:

- replay applied:
  - restored dynamic catalog provider fallback in
    `core/framework/agent_loop/prompting.py` (`build_prompt_spec(...)`).
- execution artifact:
  - `docs/ops/upstream-migration/wave15-nd5c-agentloop-prompting-execution-2026-04-25.json`
- validation:
  - targeted checks: `163 passed, 4 skipped`;
  - full regression gate: `ok=7 failed=0`.

Next active sub-lane:

- `ND-5D` event-publishing micro-lane:
  - `core/framework/agent_loop/internals/event_publishing.py`
- artifacts:
  - `docs/ops/upstream-migration/wave15-nd5d-event-publishing.patch`
  - `docs/ops/upstream-migration/wave15-nd5d-event-publishing-probe-2026-04-25.json`
  - `docs/ops/upstream-migration/wave15-nd5d-event-publishing-replay-plan-2026-04-25.md`
- probe status:
  - `git apply --check` -> `replay_ready`.

ND-5D execution result:

- replay applied:
  - restored `cache_creation_tokens` + `cost_usd` fields in
    `core/framework/agent_loop/internals/event_publishing.py`.
- execution artifact:
  - `docs/ops/upstream-migration/wave15-nd5d-event-publishing-execution-2026-04-25.json`
- validation:
  - targeted checks: `163 passed, 4 skipped`;
  - full regression gate: `ok=7 failed=0`.

Next active sub-lane:

- `ND-5E` agent-loop types micro-lane:
  - `core/framework/agent_loop/types.py`
  - `core/framework/agent_loop/internals/types.py`
- artifacts:
  - `docs/ops/upstream-migration/wave15-nd5e-agentloop-types.patch`
  - `docs/ops/upstream-migration/wave15-nd5e-agentloop-types-probe-2026-04-25.json`
  - `docs/ops/upstream-migration/wave15-nd5e-agentloop-types-replay-plan-2026-04-25.md`
  - `docs/ops/upstream-migration/wave15-nd5e-agentloop-types-execution-2026-04-25.json`
- probe status:
  - `git apply --check` -> `replay_ready`.
- validation (current):
  - targeted checks: `163 passed, 4 skipped`;
  - full regression gate: `ok=7 failed=0`.

ND-5E execution result:

- replay applied:
  - `core/framework/agent_loop/types.py`;
  - `core/framework/agent_loop/internals/types.py`.
- execution artifact:
  - `docs/ops/upstream-migration/wave15-nd5e-agentloop-types-execution-2026-04-25.json`
- validation:
  - targeted checks: `163 passed, 4 skipped`;
  - full regression gate: `ok=7 failed=0`.

ND-5F execution result:

- replay applied:
  - `core/framework/agents/discovery.py`
- execution artifact:
  - `docs/ops/upstream-migration/wave15-nd5f-agents-discovery-execution-2026-04-25.json`
- validation:
  - targeted checks:
    - `uv run --package framework pytest core/framework/server/tests/test_api.py -k "org or colony or queen" -q`
      -> `9 passed, 184 deselected`
  - full regression gate:
    - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
      -> `ok=7 failed=0`

Post-ND5F handoff:

- residual snapshot:
  - `docs/ops/upstream-migration/wave15-post-nd5f-residual-inventory-2026-04-25.json`
- residual triage:
  - `docs/ops/upstream-migration/wave15-post-nd5f-residual-triage-2026-04-25.md`
- next wave entry point:
  - `Wave16-R1` residual-governance lane (explicit keep-local allowlist + bounded replay candidate selection).

Wave16 execution continuation (R6/R7):

- `Wave16-R6` runtime warning/noise hardening:
  - execution artifact:
    - `docs/ops/upstream-migration/wave16-r6-runtime-warning-noise-hardening-execution-2026-04-25.json`
  - result:
    - expected bundled framework↔preset skill-collision warnings suppressed;
    - cancellation-timeout shutdown noise downgraded from warning to informational/debug paths;
    - targeted tests green.
- `Wave16-R7` gate stability soak:
  - execution artifact:
    - `docs/ops/upstream-migration/wave16-r7-autonomous-ops-status-flake-stabilization-execution-2026-04-25.json`
  - result:
    - deterministic ops-status stale/no-progress tests in full-suite context;
    - full regression gate stable (`ok=7 failed=0` in consecutive post-fix runs).

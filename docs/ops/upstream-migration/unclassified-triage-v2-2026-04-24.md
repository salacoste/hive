# Unclassified Delta Triage v2 (2026-04-24)

Date: 2026-04-24  
Source report: `scripts/upstream_sync_watch.sh` with
`HIVE_UPSTREAM_BASE_REF=HEAD`, `HIVE_UPSTREAM_TARGET_REF=upstream/main`  
Snapshot: `ahead=8`, `behind=53`, `other_unclassified=507`.

## Objective

Split the 507 unclassified paths into bounded lanes for item `259`:
- what can be adopted safely now (low/medium);
- what must stay deferred due architecture/runtime risk.

## Lane classification (v2)

1. `safe_docs` — 100 paths
- patterns: `docs/**`, `ai-proxy-docs/**`
- risk: low
- action: candidate for direct adoption batch.

2. `safe_scripts` — 166 paths
- patterns: `scripts/**`
- risk: low/medium (operational scripts + tests)
- action: adopt in bounded chunks with script-level smoke.

3. `safe_repo_meta` — 11 paths
- patterns: root repo meta and workflows
  (`.gitignore`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/**`, etc.)
- risk: medium (CI/runtime behavior changes)
- action: separate bounded batch with container gate.

4. `medium_tools` — 29 paths
- patterns: `tools/**`
- risk: medium (MCP registry/tooling contracts)
- action: adopt only after targeted tool registration/spec conformance tests.

5. `defer_core_runtime` — 126 paths
- patterns: `core/framework/**` (excluding server tests)
- risk: high
- reason: upstream has major graph/runtime/runner layout reshapes.
- action: defer to architecture migration lane.

6. `defer_frontend` — 31 paths
- patterns: `core/frontend/**`
- risk: high for current branch due local Telegram/WebUI contract deltas.
- action: adopt only as compatibility bundles.

7. `defer_tests` — 24 paths
- patterns: `core/tests/**`, `core/framework/server/tests/**`
- risk: medium/high (often assumes not-yet-adopted runtime changes).
- action: sync only with corresponding runtime bundles.

8. `defer_other` — 20 paths
- patterns: `automation/**`, `examples/templates/**`, `data/**`, `.hive/**`
- risk: mixed
- action: treat as opt-in; never auto-adopt `.hive` artifacts.

## Proposed bounded batches for item 259

1. Batch `259-A` (safe docs)
- include: `docs/**`, `ai-proxy-docs/**`
- applied in non-destructive mode:
  - `docs/releases/v0.10.3.md`
  - `docs/releases/v0.10.4.md`
  - `docs/skill-registry-prd.md`
- deferred in this batch:
  - mass-deletion docs patch from upstream (`docs/autonomous-factory/**`, `docs/ops/**`, `ai-proxy-docs/**`)
    to preserve local operations runbooks/backlog.
- gate:
  - `uv run python scripts/validate_backlog_markdown.py`
  - docs lint/check scripts currently used in repo.

2. Batch `259-B` (safe scripts)
- include: selected `scripts/**` + matching `scripts/tests/**`
- gate:
  - targeted script tests
  - container smoke for modified operational scripts.

3. Batch `259-C` (repo meta)
- include: `.github/workflows/**`, root meta files.
- gate:
  - `docker compose up -d --build`
  - core API health/ops endpoints.

4. Batch `259-D` (tools medium)
- include: selected `tools/**` changes not yet synced.
- gate:
  - `tools/tests/integrations/test_registration.py`
  - `tools/tests/integrations/test_spec_conformance.py`.

## Explicit deferrals (v2)

1. `core/framework/{graph,runtime,runner,...}` migration waves.
2. Frontend large bundles (`ChatPanel`, `colony-chat`, `queen-dm`) until compatibility layer is defined.
3. Test files that import symbols absent in current local runtime branch.

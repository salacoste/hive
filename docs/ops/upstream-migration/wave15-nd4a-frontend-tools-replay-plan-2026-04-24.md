# Wave 15 — ND-4A Frontend Tools Surface Replay Plan

Date: 2026-04-24
Status: executed

## Scope

Bounded files:

- `core/frontend/src/api/colonies.ts`
- `core/frontend/src/api/mcp.ts`
- `core/frontend/src/api/skills.ts`
- `core/frontend/src/components/ColonyToolsSection.tsx`
- `core/frontend/src/components/McpServersPanel.tsx`
- `core/frontend/src/components/QueenToolsSection.tsx`
- `core/frontend/src/components/ToolsEditor.tsx`
- `core/frontend/src/hooks/use-pending-queue.ts`
- `core/frontend/src/pages/skills-library.tsx`
- `core/frontend/src/pages/tool-library.tsx`
- `core/frontend/src/App.tsx`
- `core/frontend/src/components/Sidebar.tsx`
- `core/frontend/src/pages/org-chart.tsx`
- `core/frontend/src/types/colony.ts`

Patch artifact:

- `docs/ops/upstream-migration/wave15-nd4a-frontend-tools.patch`

Probe artifact:

- `docs/ops/upstream-migration/wave15-nd4a-frontend-tools-probe-2026-04-24.json`

Probe summary:

- `git apply --check` passed (`exit_code=0`) on bounded patch.

## Execution checklist

1. Apply bounded patch:
   - `git apply docs/ops/upstream-migration/wave15-nd4a-frontend-tools.patch`
2. Verify scoped diff only:
   - `git diff --numstat -- <ND-4A files>`
3. Run targeted frontend checks:
   - `cd core/frontend && npm test -- --run`
   - `cd core/frontend && npm run build`
4. Run mandatory full regression gate:
   - `HIVE_UPSTREAM_SYNC_GATE_PROFILE=full HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID=default ./scripts/upstream_sync_regression_gate.sh`
5. Record execution artifact and update backlog/docs.

## Execution result

- primary ND-4A patch replay applied.
- applied bounded reconcile follow-ups for dependent frontend API/types wiring.
- frontend test/build passed:
  - `npm test -- --run` -> `49 passed`;
  - `npm run build` -> `ok`.
- full regression gate passed: `ok=7 failed=0`.
- evidence:
  - `docs/ops/upstream-migration/wave15-nd4a-frontend-tools-execution-2026-04-24.json`.

## Rollback checklist

If needed before commit:

1. Restore ND-4A files from `HEAD`:
   - `git restore --worktree --staged -- <ND-4A files>`
2. Re-run minimal safety gate:
   - `./scripts/upstream_sync_regression_gate.sh`

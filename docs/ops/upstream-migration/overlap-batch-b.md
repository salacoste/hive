# Overlap Batch B (Frontend Operator UX)

Date: 2026-04-18

## Scope

Frontend operator overlap integration for upstream landing:

1. `core/frontend/src/pages/workspace.tsx`
2. `core/frontend/src/pages/my-agents.tsx`
3. `core/frontend/src/components/HistorySidebar.tsx`
4. `core/frontend/src/api/types.ts`
5. `core/frontend/src/api/sessions.ts`
6. `core/frontend/src/api/execution.ts`
7. `core/frontend/src/api/credentials.ts`
8. `core/frontend/src/lib/chat-helpers.ts`
9. `core/frontend/src/lib/chat-helpers.test.ts`

## Artifacts

1. Full export:
   - `docs/ops/upstream-migration/overlap-batch-b-latest.patch`
   - `docs/ops/upstream-migration/overlap-batch-b-latest.md`
2. Dependency bundle:
   - `docs/ops/upstream-migration/overlap-batch-b-dependency-bundle-latest.md`
3. Frontend overlap bundle:
   - `docs/ops/upstream-migration/overlap-batch-b-bundle-latest.md`
4. Landing rehearsal:
   - `docs/ops/upstream-migration/overlap-batch-b-landing-rehearsal-latest.md`

## Scripts

1. `scripts/upstream_overlap_batch_b_export.sh`
2. `scripts/upstream_overlap_batch_b_dependency_bundle.sh`
3. `scripts/upstream_overlap_batch_b_bundle.sh`
4. `scripts/upstream_overlap_batch_b_landing_rehearsal.sh`
5. `scripts/upstream_overlap_batch_b_bundle_apply.sh`

## Current Finding

1. Deterministic export is prepared:
   - patch and numstat report generated for all 9 overlap files.
2. Deterministic bundle path is prepared:
   - dependency bundle for operator UI closure (`components/lib/hooks + api client/agents/graphs/logs`);
   - frontend overlap bundle for Batch B files.
3. Landing rehearsal on clean `origin/main` clone:
   - applies replay + dependency + frontend bundles;
   - gate report confirms:
     - `npm ci` = `ok`;
     - operator TS smoke (`workspace/my-agents/history + dependencies`) = `ok`;
     - `chat-helpers` vitest = `ok`.
4. Full frontend build in isolated Batch B rehearsal remains `failed` (informational):
   - breakage is in out-of-scope legacy surfaces (`queen-dm`, `colony-chat`, legacy credentials/config UIs);
   - this coupling requires either:
     - broader frontend surface replay, or
     - compatibility shims while keeping operator UX scope narrow.

## Apply Step (landing branch only)

```bash
HIVE_UPSTREAM_LANDING_BRANCH=migration/upstream-wave3 \
./scripts/upstream_overlap_batch_b_bundle_apply.sh --check

HIVE_UPSTREAM_LANDING_BRANCH=migration/upstream-wave3 \
./scripts/upstream_overlap_batch_b_bundle_apply.sh --apply
```

Guardrails:

1. script exits if current branch is not `migration/upstream-wave3`;
2. script exits on dirty worktree unless `HIVE_UPSTREAM_ALLOW_DIRTY=true`.

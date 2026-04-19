# Overlap Batch B Frontend Bundle (Latest)

- Generated: 2026-04-18T02:01:26Z
- Target ref (informational): `origin/main`
- Bundle: `docs/ops/upstream-migration/replay-bundles/wave3-batch-b-frontend-20260418-020126.tar.gz`
- SHA256: `b069550518454b3d3128901d8475e016763b5e08ec51fc4bfe2a4d52bacc15b2`
- Included file count: `9`

## Included files

- `core/frontend/src/pages/workspace.tsx`
- `core/frontend/src/pages/my-agents.tsx`
- `core/frontend/src/components/HistorySidebar.tsx`
- `core/frontend/src/api/types.ts`
- `core/frontend/src/api/sessions.ts`
- `core/frontend/src/api/execution.ts`
- `core/frontend/src/api/credentials.ts`
- `core/frontend/src/lib/chat-helpers.ts`
- `core/frontend/src/lib/chat-helpers.test.ts`

## Numstat vs origin/main

| File | + | - |
|---|---:|---:|
| `core/frontend/src/api/credentials.ts` | 40 | 39 |
| `core/frontend/src/api/execution.ts` | 4 | 13 |
| `core/frontend/src/api/sessions.ts` | 73 | 30 |
| `core/frontend/src/api/types.ts` | 115 | 38 |
| `core/frontend/src/components/HistorySidebar.tsx` | 440 | 0 |
| `core/frontend/src/lib/chat-helpers.test.ts` | 13 | 1 |
| `core/frontend/src/lib/chat-helpers.ts` | 4 | 48 |
| `core/frontend/src/pages/my-agents.tsx` | 138 | 0 |
| `core/frontend/src/pages/workspace.tsx` | 6125 | 0 |

## Apply in clean probe/landing clone

```bash
tar -xzf docs/ops/upstream-migration/replay-bundles/wave3-batch-b-frontend-20260418-020126.tar.gz
```

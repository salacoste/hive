# Landing Branch Bootstrap Snapshot

- Generated: 2026-04-17T21:27:19Z
- Mode: print-only
- Base branch: main
- Target ref: origin/main
- Landing branch: migration/upstream-wave3
- Ahead/behind (`main...origin/main`): 0	225
- Local dirty paths: 214
- Dirty ∩ upstream overlap paths: 68

## Replay Domains (Wave 3)

1. `core/framework/server/project_*`
2. `core/framework/server/routes_projects.py`
3. `core/framework/server/routes_autonomous.py`
4. `core/framework/server/telegram_bridge.py`
5. `core/framework/server/autonomous_pipeline.py`
6. `core/frontend/src/api/projects.ts`
7. `core/frontend/src/api/autonomous.ts`
8. `scripts/autonomous_*`, `scripts/acceptance_*`, `scripts/verify_access_stack.sh`
9. `docs/LOCAL_PROD_RUNBOOK.md`, `docs/autonomous-factory/*`

## Apply Commands

```bash
git fetch origin --prune
git checkout -B migration/upstream-wave3 origin/main
```

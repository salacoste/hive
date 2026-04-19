# 04. Operations Runbook

Acceptance automation reference:

- `../ops/acceptance-automation-map.md`
- `../LOCAL_PROD_RUNBOOK.md`

## Daily Start Checks

1. platform health
- `docker compose ps`
- verify all required services are healthy

2. Hive Core logs
- `docker compose logs --tail=200 hive-core`
- verify no startup errors

3. control surfaces
- web endpoint alive
- Telegram bot responds to `/status`

4. integration checks
- GitHub auth valid
- secrets backend reachable
- queue/redis healthy

## Standard Operations

### Create and run coding task

1. create session/task
2. assign repository and objective
3. validate generated plan
4. allow implementation
5. validate output and PR

### Stop runaway execution

1. use Telegram `Stop` or `Cancel`
2. if still active, stop task in orchestrator
3. kill runner container

### Restart Hive Core

1. `docker compose restart hive-core`
2. verify `Telegram bridge started`
3. run quick task health check

## Incident Playbooks

### Incident A: GitHub push/PR failures

1. verify GitHub app token scope and expiration
2. verify branch protection constraints
3. retry task with same branch
4. if repeated, disable autonomous merge and switch to manual PR completion

### Incident B: Secrets unavailable

1. check secret manager connectivity
2. rotate fallback token if policy allows
3. freeze high-risk tasks until secrets path is restored

### Incident C: DB operation risk

1. ensure task is read-only
2. if write required, enforce approval gate
3. run migration only in controlled pipeline stage

### Incident D: Infinite retry/tool loop

1. cancel current turn
2. collect event timeline
3. add policy rule for retry cap
4. reopen task with patched constraints

## Audit and Evidence

Per task retain:

- plan
- patch summary
- validation outputs
- access log extracts
- PR link and merge status

Retention target:

- 30-90 days minimum for operational forensics

## Backup and Recovery

1. backup:
- Hive state volumes
- task metadata and logs
- policy config

2. restore drill:
- restore to staging
- replay representative tasks
- verify deterministic behavior

## KPIs (Weekly)

1. task success rate
2. median cycle time (task -> PR)
3. validation failure rate
4. rollback/reopen count
5. manual intervention ratio

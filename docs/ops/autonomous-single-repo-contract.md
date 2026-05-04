# Autonomous Single-Repo E2E Contract

Цель: зафиксировать единый, проверяемый операторский контракт для цикла
`project onboarding -> backlog task -> execute-next -> run-until-terminal -> report`
в container-first режиме.

## 1. Канонический E2E путь (API)

1. Onboarding проекта
- Endpoint: `POST /api/projects/{project_id}/onboarding`
- Источник: `core/framework/server/routes_projects.py`
- Успех:
  - `200` и `ready=true` (проект готов к исполнению),
  - `202` и `ready=false` (onboarding завершён частично, требуются ручные действия).

2. Создание backlog задачи
- Endpoint: `POST /api/projects/{project_id}/autonomous/backlog`
- Источник: `core/framework/server/routes_autonomous.py`
- Успех: `201`, создаётся task со статусом `todo`.

3. Диспетчеризация + цикл исполнения
- Endpoint: `POST /api/projects/{project_id}/autonomous/execute-next`
- Источник: `core/framework/server/routes_autonomous.py`
- Поведение:
  - выбирает следующую задачу (`priority_then_created_at`),
  - создаёт run при отсутствии активного,
  - запускает внутренний `run-until-terminal` bounded по `max_steps`.

4. Доведение run до terminal
- Endpoint: `POST /api/projects/{project_id}/autonomous/runs/{run_id}/run-until-terminal`
- Источник: `core/framework/server/routes_autonomous.py`
- Контракт ответа:
  - `terminal` (`true|false`),
  - `terminal_status` (`completed|failed|escalated|null`),
  - `current_stage`, `status`, `steps_executed`, `steps`.

5. Финальный отчёт
- Endpoint: `GET /api/projects/{project_id}/autonomous/runs/{run_id}/report`
- Источник: `core/framework/server/routes_autonomous.py`
- Контракт: `report` + `stages` (включая checks/risk summary при наличии).

## 2. Нейминг стадий: operator-flow vs runtime

Operator-facing execution template:
- `design`
- `implement`
- `review`
- `validate`

Runtime pipeline store (`STAGES`):
- `execution`
- `review`
- `validation`

Нормализованное соответствие:
- `design + implement` -> `execution`
- `review` -> `review`
- `validate` -> `validation`

Источник правды:
- `core/framework/server/project_execution.py` (operator flow template),
- `core/framework/server/autonomous_pipeline.py` (`STAGES=("execution","review","validation")`).

## 3. Fallback policy matrix (locked)

1. Onboarding не готов (`ready=false`)
- Базовый API-контракт: `202` + `ready=false`.
- E2E smoke контракт:
  - default: разрешён `manual_deferred_onboarding`,
  - strict mode (`--strict-onboarding`): сценарий считается failed.
- Источник: `scripts/autonomous_delivery_e2e_smoke.py`.

2. Нет GitHub токена на `review/validation`
- Для `loop_tick`/`auto-next`:
  - при `HIVE_AUTONOMOUS_AUTO_NEXT_FALLBACK=manual_pending` -> `202`, `action=manual_evaluate_required`,
  - иначе -> hard error (`400`).
- Источник: `core/framework/server/routes_autonomous.py`.

3. Не найдены checks в GitHub evaluate
- Политика берётся из `execution_template.no_checks_policy`
  (или env `HIVE_AUTONOMOUS_GITHUB_NO_CHECKS_POLICY`):
  - `error` -> `400`,
  - `manual_pending` -> `202` + manual evaluate required,
  - `success` -> stage считается pass с `total=0`.
- Источник: `core/framework/server/routes_autonomous.py`.

4. Ошибка GitHub API при evaluate
- `evaluate/github`: `502` (или `400` для invalid input).
- `loop_tick`/`auto-next` могут деградировать в manual deferred (`202`),
  если включён fallback `manual_pending`.
- Источник: `core/framework/server/routes_autonomous.py`.

5. Определение terminal execution после рестарта
- Приоритет:
  - terminal execution events,
  - terminal worker completion fallback,
  - active execution ids,
  - cold-restart inference по `worker_completed` без downstream activations.
- Источник: `core/framework/server/routes_autonomous.py`.

## 4. Acceptance criteria (DoD для single-repo контракта)

1. Один и тот же путь воспроизводим через API без ручной интерпретации:
- onboarding -> backlog create -> execute-next -> run-until-terminal -> report.

2. Stage semantics не расходится между шаблоном и runtime:
- operator stages (`design/implement/review/validate`) и runtime stages
  (`execution/review/validation`) явно задокументированы и применяются консистентно.

3. Fallback-поведение детерминировано:
- onboarding deferred,
- no checks policy,
- missing token / GitHub evaluate fallback.

4. Контракт проверяется container-first smoke.

## 5. Container-first smoke команды

```bash
# 1) E2E smoke real repo scenario
./scripts/hive_ops_run.sh uv run --no-project scripts/autonomous_delivery_e2e_smoke.py \
  --skip-template \
  --real-project-id <project_id> \
  --real-repository <repo_url> \
  --require-terminal-success \
  --github-no-checks-policy success

# 2) Ops snapshot
./scripts/hive_ops_run.sh curl -sS \
  "http://127.0.0.1:8787/api/autonomous/ops/status?project_id=<project_id>&include_runs=true"

# 3) Run-cycle compact report
./scripts/hive_ops_run.sh curl -sS -X POST \
  "http://127.0.0.1:8787/api/autonomous/loop/run-cycle/report" \
  -H "Content-Type: application/json" \
  -d "{\"project_ids\":[\"<project_id>\"],\"max_steps_per_project\":1}"
```

## 6. Related docs

- `docs/autonomous-factory/20-multi-project-autonomy-blueprint.md`
- `docs/LOCAL_PROD_RUNBOOK.md`
- `docs/ops/phase-e-closure-checklist.md`

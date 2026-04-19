# 09. Autonomous Control Plane

## Objective

Сделать поведение Hive предсказуемым и управляемым для автономной разработки:

- единый формат входной задачи;
- policy-driven исполнение;
- явные risk gates;
- обязательные доказательства результата.

## Control Plane Artifacts

1. `automation/hive.factory-policy.yaml`
- Глобальные правила фабрики.
- Риск-классы, лимиты ретраев, бюджеты, обязательные проверки.

2. `automation/hive.task.yaml`
- Контракт конкретной задачи.
- Цель, критерии приёмки, ограничения, репозиторий, уровень риска.

3. `automation/hive.manifest.yaml`
- Репозиторный профиль (команды, required checks, секреты, доступы).

## Execution Contract

Каждая задача проходит этапы:

1. Intake
- загрузка `hive.task.yaml`;
- валидация обязательных полей;
- сверка с `hive.factory-policy.yaml`.

2. Plan
- план реализации;
- список файлов/модулей под изменения;
- список рисков и required approvals.

3. Implement
- изолированный workspace;
- отдельная ветка (`hive/task/*`);
- запрет на действия вне policy.

4. Validate
- команды из `hive.manifest.yaml`;
- security/smoke checks;
- сбор артефактов (логи, статус, отчёт).

5. Publish
- PR с шаблонным отчётом;
- ссылки на артефакты;
- статус risk gates.

## Risk Tiers

- `low`: безопасные code-only изменения, автозапуск без ручного approval.
- `medium`: code + конфиг, нужен post-plan confirmation.
- `high`: DB schema/infra/prod-конфиги, обязательный pre-approval.
- `critical`: запрещено в автономном режиме.

## Hard Guards

- запрет force-push в защищённые ветки;
- запрет прямых изменений в production DB;
- запрет deploy в production без approval;
- запрет неразрешённых доменов (egress allowlist).

## Human Control Points

Минимум 3 контролируемые точки:

1. `plan_approved`
2. `run_approved` (для medium/high)
3. `merge_approved` (всегда по policy репозитория)

## Evidence Required Per Task

- task contract snapshot;
- final plan;
- diff summary;
- validation outputs;
- PR URL;
- risk/decision log.

## Minimal API of Commands (Operator View)

Через Telegram/Web:

- `new task` -> создать сессию и привязать `hive.task.yaml`
- `plan` -> построить/показать план
- `run` -> старт исполнения
- `status` -> текущий этап + risk + blockers
- `cancel` -> остановка

## KPI for Autonomous Coding

- Task success rate
- Time to first PR
- Validation pass rate
- Manual intervention ratio
- Reopen/rollback rate


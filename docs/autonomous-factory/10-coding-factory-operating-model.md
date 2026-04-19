# 10. Coding Factory Operating Model

Практический режим, когда основная цель - автономная разработка кода по задачам владельца.

## 1) Как выдавать задачи

Используйте шаблон `automation/hive.task.yaml` и заполняйте:

- `repository.name`
- `objective`
- `acceptance_criteria`
- `task.risk_tier`
- `constraints`
- `done_definition`

Без `acceptance_criteria` задача не запускается.

## 2) Как Hive выполняет задачу

1. Создаёт отдельную ветку.
2. Делает план + риск-анализ.
3. Выполняет изменения.
4. Запускает lint/typecheck/tests/build.
5. Формирует PR с отчётом.

## 3) Как обрабатывать разные типы задач

- Feature: обязательный smoke + regression тесты.
- Bugfix: mandatory reproduction note + fixed-by evidence.
- Refactor: performance/behavior parity checks.
- Docs-only: tests optional, link/format checks required.

## 4) Стратегия по репозиториям

- Один репозиторий -> один manifest.
- Монорепо -> по одному manifest на domain/service при необходимости.
- Любой repo onboarding завершается dry-run задачей.

## 5) Strategy for Access

- GitHub: write only to task branches.
- DB: readonly by default.
- External APIs: allowlist only.
- Secrets: from credential store/env sync, no plaintext in tasks.

## 6) Run Modes

- `assist`: оператор подтверждает каждый этап.
- `semi-auto`: авто-run low risk, approval для medium/high.
- `auto`: full cycle для low/medium по policy.

Рекомендация для старта: `semi-auto`.

## 7) Incident Rules

- Больше 2 неудачных ретраев подряд -> `blocked`, требуется оператор.
- Любая попытка high-risk action без approval -> hard stop.
- Ошибка в валидации -> PR не создаётся до прохождения gates.

## 8) Definition of Done

Задача считается завершённой только когда:

- acceptance criteria выполнены;
- required checks зелёные;
- PR опубликован;
- evidence bundle сохранён.

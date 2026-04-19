# 11. Project-Scoped Sessions

Hive теперь поддерживает модель:

- `Project` = логический контейнер разработки (репозиторий/приложение/продуктовый поток)
- `Session` = конкретный рабочий runtime внутри выбранного проекта

Это позволяет вести параллельную разработку нескольких приложений без смешивания контекста.

## API

### Projects

- `GET /api/projects` — список проектов + `default_project_id`
- `POST /api/projects` — создать проект
- `GET /api/projects/{project_id}` — получить проект
- `PATCH /api/projects/{project_id}` — обновить проект
- `DELETE /api/projects/{project_id}` — удалить проект (`?force=1` если есть активные сессии)
- `GET /api/projects/{project_id}/sessions` — live-сессии проекта

### Sessions (project-aware)

- `POST /api/sessions` поддерживает `project_id`
- `GET /api/sessions?project_id=...` фильтрует live-сессии
- `GET /api/sessions/history?project_id=...` фильтрует историю по проекту

В session payload возвращается `project_id`.

## Telegram

Новые команды:

- `/projects` — список проектов
- `/project <id>` — выбрать активный проект чата
- `/newproject <name>` — создать проект и сразу переключиться

Поведение:

- `/new` создаёт новую сессию в активном проекте чата.
- `/sessions` показывает только сессии активного проекта.
- `/status` показывает текущий проект + текущую сессию.

## Operational Rule

Рекомендация для фабрики:

- один продукт/репозиторий = один `project_id`;
- все задачи/сессии по этому продукту запускаются только в его проекте;
- cross-project задачи оформлять отдельным orchestration-task, но не смешивать в одной сессии.


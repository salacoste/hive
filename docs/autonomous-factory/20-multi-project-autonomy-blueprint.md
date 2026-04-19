# 20. Multi-Project Autonomy Blueprint

Цель: зафиксировать единый production-ready стандарт для автономной разработки нескольких проектов в Hive, полностью в container-first режиме.

## 1) Инварианты архитектуры (не нарушаются)

1. `project` — граница изоляции.
2. Каждая `session` всегда привязана к одному `project_id`.
3. Pipeline запускается только из backlog проекта: `todo -> in_progress -> done|blocked`.
4. Риск-политика применяется на уровне проекта (`policy_binding`), не на уровне чата/оператора.
5. Автономный flow проекта: `design -> implement -> review -> validate`.

## 2) Контракт проекта (минимум для старта)

Для каждого проекта фиксируем:

1. Репозиторий (`repository`, `workspace_path`, `manifest`).
2. Лимит параллелизма (`max_concurrent_runs`).
3. Policy binding (`risk_tier`, retry/budget).
4. Execution template (stage flow + retry/escalation).
5. Retention policy (история/архив).

Шаблоны:

- `docs/autonomous-factory/templates/project-create.json`
- `docs/autonomous-factory/templates/project-onboarding.json`
- `docs/autonomous-factory/templates/project-policy-binding.json`
- `docs/autonomous-factory/templates/project-execution-template.json`
- `docs/autonomous-factory/templates/autonomous-backlog-task.json`

## 3) Рекомендуемый model routing (зафиксирован)

Используем текущие профили runtime:

1. `strategy_heavy`: `claude-opus-4-6` -> fallback `gpt-5.4`
2. `implementation`: `openai/gemini-3.1-pro-high` -> fallback `openai/glm-5.1`
3. `documentation`: `openai/glm-5.1`
4. `review_validation`: `gpt-5.3-codex`

## 4) Container-First bootstrap (одинаково на любой машине)

Предусловия:

1. `docker compose up -d`
2. `hive-core` в `healthy`
3. `.env` заполнен ключами MCP/LLM

### 4.0 Toolchain profile with explicit confirmation

Перед onboarding определяем нужные компиляторы/рантаймы и применяем профиль только после явного подтверждения:

```bash
# Dry-run: prints required confirmation token
./scripts/apply_hive_toolchain_profile.sh \
  --repository https://github.com/salacoste/mcp-n8n-workflow-builder

# Apply only with explicit token
./scripts/apply_hive_toolchain_profile.sh \
  --repository https://github.com/salacoste/mcp-n8n-workflow-builder \
  --apply --confirm APPLY_NODE
```

### Шаг 1. Создать проект

```bash
docker compose exec -T hive-core sh -lc '
curl -sS -X POST "http://127.0.0.1:8787/api/projects" \
  -H "Content-Type: application/json" \
  --data-binary @/app/docs/autonomous-factory/templates/project-create.json
'
```

### Шаг 2. Onboarding репозитория

```bash
docker compose exec -T hive-core sh -lc '
curl -sS -X POST "http://127.0.0.1:8787/api/projects/<project_id>/onboarding" \
  -H "Content-Type: application/json" \
  --data-binary @/app/docs/autonomous-factory/templates/project-onboarding.json
'
```

### Шаг 3. Применить policy binding

```bash
docker compose exec -T hive-core sh -lc '
curl -sS -X PATCH "http://127.0.0.1:8787/api/projects/<project_id>/execution-template" \
  -H "Content-Type: application/json" \
  --data-binary @/app/docs/autonomous-factory/templates/project-policy-binding.json
'
```

### Шаг 4. Применить execution template

```bash
docker compose exec -T hive-core sh -lc '
curl -sS -X PATCH "http://127.0.0.1:8787/api/projects/<project_id>/execution-template" \
  -H "Content-Type: application/json" \
  --data-binary @/app/docs/autonomous-factory/templates/project-execution-template.json
'
```

### Шаг 5. Добавить задачу в backlog

```bash
docker compose exec -T hive-core sh -lc '
curl -sS -X POST "http://127.0.0.1:8787/api/projects/<project_id>/autonomous/backlog" \
  -H "Content-Type: application/json" \
  --data-binary @/app/docs/autonomous-factory/templates/autonomous-backlog-task.json
'
```

### Шаг 6. Запустить автономный цикл

```bash
docker compose exec -T hive-core sh -lc '
curl -sS -X POST "http://127.0.0.1:8787/api/projects/<project_id>/autonomous/execute-next" \
  -H "Content-Type: application/json" \
  -d "{\"auto_start\":true,\"max_steps\":8}"
'
```

### Шаг 7. Проверить статус и отчет

```bash
docker compose exec -T hive-core sh -lc '
curl -sS "http://127.0.0.1:8787/api/autonomous/ops/status?project_id=<project_id>&include_runs=true"
'
```

```bash
docker compose exec -T hive-core sh -lc '
curl -sS -X POST "http://127.0.0.1:8787/api/autonomous/loop/run-cycle/report" \
  -H "Content-Type: application/json" \
  -d "{\"project_ids\":[\"<project_id>\"],\"auto_start\":false,\"max_steps_per_project\":1}"
'
```

## 5) Операционная модель для нескольких проектов

1. Один репозиторий/продукт = один `project_id`.
2. Не запускать cross-project задачи в одной сессии.
3. Для каждого проекта держать отдельный backlog, policy и concurrency limit.
4. `semi-auto` как базовый режим: execution автоматический, review/validation с gates.
5. Ежедневно: `ops/status`, `run-cycle/report`, Telegram `/autodigest`.

## 6) Gate-критерии готовности проекта к автономному режиму

Проект считается готовым, когда:

1. `onboarding` завершен (`ready=true`).
2. `policy_binding` и `execution_template` установлены.
3. Минимум один backlog task проходит до terminal state без ручного дебага кода.
4. `ops/status` без `stuck_runs` и `loop_stale`.
5. MCP health-check по требуемым интеграциям проекта зеленый.

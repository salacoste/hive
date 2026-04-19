# 12. Backlog Task List

Цель: централизованный backlog для автономной фабрики разработки на Hive.

Статусы:
- `todo`
- `in_progress`
- `blocked`
- `done`

Приоритеты:
- `P0` — критично для запуска/стабильности
- `P1` — важно для масштабирования
- `P2` — улучшения

## P0

1. `P0` Web UI: Project Selector + Create Project
- Status: `done`
- Scope:
  - добавить selector текущего проекта в workspace UI;
  - добавить создание проекта из UI;
  - все `create/list/history sessions` выполнять с `project_id`.
- Done when:
  - пользователь в UI выбирает проект и видит только его сессии;
  - новая сессия всегда создаётся в выбранном проекте.

2. `P0` Telegram Project Control UX
- Status: `done`
- Scope:
  - кнопки для `Projects`, `Switch Project`, `New Project`;
  - inline-выбор проекта без ручного ввода команды.
- Done when:
  - полный project lifecycle доступен из Telegram без ввода ID вручную.

3. `P0` Project-Aware Session Resume Rules
- Status: `done`
- Scope:
  - проверить/докрутить cold-resume поведение при project фильтрации;
  - добавить тест-кейсы на `history?project_id=...`.
- Progress:
  - добавлены тест-кейсы API на `project_id` фильтрацию live/history (`core/framework/server/tests/test_api.py`);
  - подтверждён merge live+disk в `/api/sessions/history` с backfill `project_id` из live-сессии.
  - добавлен server-side guard против cross-project `queen_resume_from` в `SessionManager`;
  - добавлены unit-тесты на reject/allow resume по границе проекта.
- Done when:
  - восстановление сессий не пересекает границы проектов.

4. `P0` API/Server Tests for Projects
- Status: `done`
- Scope:
  - тесты `/api/projects` CRUD;
  - тесты `POST /api/sessions` c `project_id`;
  - тесты фильтрации live/history по `project_id`.
- Progress:
  - добавлены CRUD-тесты `/api/projects` + delete-conflict/force + `/api/projects/{id}/sessions`;
  - добавлен тест `POST /api/sessions` (queen-only) с проверкой прокидывания `project_id`;
  - добавлены и проходят тесты фильтрации `/api/sessions` и `/api/sessions/history` по `project_id`.
- Done when:
  - тесты проходят стабильно в CI.

## P1

5. `P1` Per-Project Task Queue and Concurrency Limits
- Status: `done`
- Scope:
  - лимиты параллелизма на проект;
  - очередь задач с приоритетами.
- Progress:
  - добавлен server-side per-project concurrency gate для `trigger/resume/replay`;
  - при достижении лимита: `409` (если `queue_if_busy=false`) или постановка в очередь (`202`);
  - добавлена in-memory priority queue + background dispatcher для автозапуска queued задач;
  - добавлен API `GET /api/projects/{project_id}/queue` для наблюдения очереди/recent dispatches;
  - лимит проекта вынесен в metadata проекта: `max_concurrent_runs` (create/update API + validation);
  - gate использует project override, fallback на `HIVE_PROJECT_MAX_CONCURRENT_RUNS`;
  - добавлены и проходят API тесты на busy/reject и busy/queue сценарии.
- Done when:
  - нет конфликтующих параллельных запусков внутри проекта.

6. `P1` Project-Level Policies
- Status: `done`
- Scope:
  - policy overrides на проект (`risk_tier`, retry limit, budget);
  - наследование от глобального factory policy.
- Progress:
  - добавлен storage полей `policy_overrides` на проект;
  - добавлены endpoints:
    - `GET /api/projects/{id}/policy` (global + overrides + effective)
    - `PATCH /api/projects/{id}/policy` (partial override updates);
  - добавлена валидация override значений (`risk_tier`, `retry_limit_per_stage`, `budget_limit_usd_monthly`);
  - inheritance реализован через загрузку глобального policy YAML (env `HIVE_FACTORY_POLICY_PATH` + fallbacks);
  - добавлен enforcement в execution-gate: при `risk_controls.allowed=false` запуск `trigger/resume/replay` блокируется (`403`);
  - добавлены и проходят API тесты на inheritance и invalid policy values.
- Done when:
  - проект может иметь собственные безопасные ограничения.

7. `P1` Project Onboarding Wizard
- Status: `done`
- Scope:
  - привязка GitHub repo, базовых checks и manifest;
  - dry-run task автоматом после onboarding.
- Progress:
  - добавлен endpoint `POST /api/projects/{id}/onboarding` с единым onboarding flow;
  - в Web UI (`workspace`) создание проекта поддерживает опцию `Run project onboarding after create` (workspace path + stack);
  - flow включает:
    - привязку/обновление `repository` проекта;
    - нормализацию GitHub slug (`owner/repo`) из URL/SSH;
    - базовые checks (`workspace exists`, `.git`, `README.md`, `manifest`);
    - автогенерацию `automation/hive.manifest.yaml` (stack-aware defaults + override команд);
    - автоматический dry-run command после onboarding с отчетом статуса/логов;
  - добавлены и проходят API тесты onboarding (happy-path + invalid stack).
- Done when:
  - новый проект подключается за один flow.

## P2

8. `P2` Project Metrics Dashboard
- Status: `done`
- Scope:
  - KPI по каждому проекту (success rate, cycle time, intervention ratio).
- Progress:
  - добавлен endpoint `GET /api/projects/{id}/metrics` с project-level KPI агрегацией;
  - добавлен endpoint `GET /api/projects/metrics` для сравнения KPI между проектами;
  - считаются `success_rate`, `cycle_time_seconds_p50`, `cycle_time_seconds_avg`, `intervention_ratio`;
  - метрики строятся по persisted sessions/events (`~/.hive/queen/session/*`) с фильтрацией по `project_id`;
  - frontend API дополнен `projectsApi.metrics(...)` для последующей визуализации в dashboard;
  - frontend API дополнен `projectsApi.compareMetrics(...)` для ranking/comparison views;
  - в `workspace` добавлен компактный KPI-блок текущего проекта (Exec/SR/P50/HITL + refresh);
  - добавлена отдельная `Project KPI Board` панель (таблица по всем проектам + sort + refresh);
  - добавлены и проходят API тесты на `project metrics` и `projects metrics comparison`.
- Done when:
  - есть сравнение качества/скорости между проектами.

9. `P2` Project Templates
- Status: `done`
- Scope:
  - шаблоны для frontend/backend/fullstack onboarding.
- Progress:
  - добавлен backend каталог шаблонов onboarding (`frontend-web`, `backend-python-api`, `fullstack-platform`);
  - добавлен endpoint `GET /api/projects/templates`;
  - `POST /api/projects/{id}/onboarding` поддерживает `template_id` и применяет template defaults (stack/repo_type/commands/required_checks/dry_run command) с возможностью override из payload;
  - в Web UI (`Create Project`) добавлен выбор `Template profile` с автоподстановкой stack;
  - frontend API дополнен `projectsApi.templates()` и `template_id` в onboarding payload;
  - добавлены и проходят API тесты на templates endpoint и template-driven onboarding.
- Done when:
  - можно создать проект из профиля стека.

10. `P2` Archival and Retention per Project
- Status: `done`
- Scope:
  - retention-политики и архив истории на проект.
- Progress:
  - добавлена поддержка `retention_policy` в project metadata (store/create/update);
  - добавлены endpoints:
    - `GET /api/projects/{id}/retention` (defaults + overrides + effective + candidate plan),
    - `PATCH /api/projects/{id}/retention` (partial updates/reset overrides),
    - `POST /api/projects/{id}/retention/apply` (dry-run/apply archive/delete);
  - реализован planner с per-project фильтрацией, age cutoff и `min_sessions_to_keep`;
  - реализован apply flow с архивацией в `~/.hive/queen/archive/<project_id>/...` (или delete при `archive_enabled=false`);
  - в Web UI добавлен `Project Retention` control center (policy edit + dry-run + apply + candidate preview);
  - в Top Bar добавлен `Eligible N` retention-risk индикатор с подсветкой;
  - добавлены и проходят API тесты на retention inheritance/override и archive apply.
- Done when:
  - история/артефакты управляются независимо по проектам.

11. `P2` Telegram Retention Digest and Controls
- Status: `done`
- Scope:
  - retention-статус и digest в Telegram;
  - ежедневные proactive напоминания по backlog retention.
- Progress:
  - добавлены команды `/retention` и `/digest` в bot commands/help;
  - в inline status-кнопки добавлены `🗂 Retention` и `📦 Digest`;
  - добавлен daily loop c env-настройками:
    - `HIVE_TELEGRAM_RETENTION_DIGEST_ENABLED`
    - `HIVE_TELEGRAM_RETENTION_DIGEST_HOUR`;
  - digest отправляется только при наличии backlog (`eligible > 0`) и не дублируется чаще 1 раза в день на чат.
- Done when:
  - оператор получает retention alerts и может проверять backlog из Telegram без Web UI.

## Current Focus (Wave 12 upstream migration)

Master plans (fixed scope):

- `docs/autonomous-factory/13-master-implementation-plan.md`
- `docs/autonomous-factory/21-upstream-migration-wave3-plan.md`

Execution snapshot (as of April 19, 2026):

- items `12..240` are completed (`done=240`);
- upstream migration wave queued as `232..240`;
- active execution:
  - `in_progress=[]`;
  - `blocked=[]`;
  - `todo=[]`;
- baseline migration references:
  - `docs/ops/upstream-migration/baseline-2026-04-17.md`;
  - `docs/ops/upstream-migration/latest.md`.

Current Focus items:

1. Wave 12 cutover/sign-off is closed (`all wave items = done`).
2. Current focus cleared (no active `in_progress` items).
3. Use this section as baseline for next explicitly approved execution wave.

## Execution Wave: Autonomous Factory Hardening (operator requested)

12. `P0` Telegram Bridge Live Smoke Test (E2E)
- Status: `done`
- Scope:
  - прогон `/status`, `/sessions`, и обычного текста через Telegram;
  - проверить полный E2E-путь: update -> bridge -> queen/session -> reply;
  - зафиксировать expected/actual в runbook с примерами команд.
- Progress:
  - добавлен `Telegram Bridge Live Smoke Checklist (E2E)` в `docs/LOCAL_PROD_RUNBOOK.md`;
  - включён live log monitor для bridge-событий;
  - выполнен live smoke прогон: `/status`, `/sessions`, `ping bridge`;
  - в логах подтверждён полный E2E-путь (`received` -> `injected chat` -> `sent message`) без `ERROR/Traceback`.
- Done when:
  - команды и обычный текст стабильно отрабатывают без ошибок в логах;
  - есть подтверждённый smoke checklist для повторного прогона.

13. `P0` Production MCP Profile + Health Checks
- Status: `done`
- Scope:
  - финализировать и проверить MCP-подключения: `github`, `google`, `web search/scrape`, `files-tools`;
  - устранить silent-fail кейсы регистрации MCP tools;
  - добавить health-check сценарии для каждого MCP и единый status summary.
- Progress:
  - выполнен credential audit по целевым tools (`web_search`, `web_scrape`, `github_create_issue`, `google_docs_get_document`, `telegram_send_message`) — missing `0`;
  - выполнен access-stack health check (`verify_access_stack.sh`) — `GitHub/Telegram/Google/Redis/Postgres/refresher` в статусе `OK`;
  - добавлен единый health summary скрипт `scripts/mcp_health_summary.py` (github/google/web search/web scrape/files-tools);
  - подтверждён `status: ok` (`5/5`) по `mcp_health_summary.py --since-minutes 20`;
  - обновлён `GOOGLE_ACCESS_TOKEN` через `google_token_auto_refresh.sh`, после чего Google health-check проходит;
  - `files-tools` zero-tools сценарий переведён в allowed mode (без retry-fail).
- Done when:
  - каждый MCP проходит health-check;
  - при деградации есть явная диагностика в API/логах.

14. `P1` Projects Architecture Closure (Isolation + Policies + Templates)
- Status: `done`
- Scope:
  - довести до production-state модель `project -> sessions -> artifacts`;
  - подтвердить изоляцию workspace и policy-ограничений между проектами;
  - закрепить шаблон исполнения `design -> implement -> review` как стандартный flow проекта.
- Done when:
  - проекты изолированы по данным, сессиям и run-контролю;
  - для каждого проекта доступен единый execution template.
- Progress:
  - в onboarding manifest закреплён стандартный execution flow:
    `design -> implement -> review -> validate`;
  - default stage profiles добавлены в manifest (`strategy_heavy`, `implementation`, `review_validation`);
  - добавлен retry/escalation scaffold в manifest (`max_retries_per_stage`, `escalate_on`);
  - обновлены onboarding тесты API с проверкой нового execution section;
  - добавлены project-level API endpoints для явного управления execution template и policy binding:
    - `GET /api/projects/{id}/execution-template`
    - `PATCH /api/projects/{id}/execution-template`;
  - синхронизирован `policy_binding` с `policy_overrides` для единого effective policy;
  - в Web UI (`workspace`) добавлен модальный `Project Execution Template` control center (`Flow`).
  - в Web UI (`Project Execution Template`) добавлены project-level GitHub controls:
    - `GitHub Default Ref` (`execution_template.github.default_ref`);
    - `GitHub No-Checks Policy` (`error|manual_pending|success`);
    - effective summary для GitHub ref/policy.
  - frontend API/types расширены под `execution_template.github.*` и top-level aliases
    (`default_ref/default_branch/ref/branch/no_checks_policy`) для стабильного contract с backend.
  - Validation (April 12, 2026):
    - container tests:
      - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "execution_template or autonomous" -q` -> `45 passed`;
    - containerized frontend build:
      - `docker run --rm -v "$PWD":/work -w /work/core/frontend node:22-bookworm bash -lc 'npm ci --no-audit --no-fund && npm run build'`
        -> success.

15. `P1` Autonomous Development Pipeline
- Status: `done`
- Scope:
  - настроить pipeline `backlog -> execution agent -> code review (gpt-5.3-codex) -> validation -> PR/report`;
  - определить входной task contract и выходные артефакты по стадиям;
  - добавить правила retries/escalation между стадиями.
- Done when:
  - pipeline исполняет задачи из backlog end-to-end;
  - по каждому запуску формируется структурированный отчёт и PR-ready output.
- Progress:
  - добавлен persistent autonomous pipeline store: `~/.hive/server/autonomous_pipeline.json`;
  - добавлены API endpoints:
    - backlog: `GET/POST/PATCH /api/projects/{id}/autonomous/backlog[...]`
    - runs: `GET/POST /api/projects/{id}/autonomous/runs[...]`
    - stage advance: `POST /api/projects/{id}/autonomous/runs/{run_id}/advance`;
  - реализованы stage transitions `execution -> review -> validation` с retries/escalation на основе project execution template;
  - добавлено авто-обновление статуса backlog task (`done`/`blocked`) по финалу pipeline run.
  - добавлен frontend API `core/frontend/src/api/autonomous.ts` и UI control center `Auto` в `workspace`:
    - создание backlog tasks;
    - запуск pipeline run по задаче;
    - ручной advance текущей стадии (`success|failed`) с notes;
    - просмотр stage states/attempts/report.
  - `execution` stage можно привязать к live session (`session_id`) при старте run:
    - сервер запускает реальный worker execution (`entry_point=default`) с task contract payload;
    - `execution_id` фиксируется в stage artifacts.
  - добавлен финальный report endpoint:
    - `GET /api/projects/{id}/autonomous/runs/{run_id}/report`.
  - добавлен checks-driven evaluation endpoint:
    - `POST /api/projects/{id}/autonomous/runs/{run_id}/evaluate`
    - вычисляет result по checks (`all_passed -> success`, иначе `failed`) и применяет retry/escalation policy.
  - report расширен до PR-ready структуры:
    - `task` contract, `pipeline` states/attempts, `checks` summary (review/validation), `artifacts`, `pr` metadata, terminal `risks`.
  - в UI добавлен `Evaluate By Checks` (textarea checks `name:pass|fail`) для review/validation без ручного result тумблера.
  - добавлен GitHub checks evaluate endpoint:
    - `POST /api/projects/{id}/autonomous/runs/{run_id}/evaluate/github`
    - подтягивает checks из GitHub API по `repository/ref` и применяет stage result автоматически;
    - поддерживает fallback: если `ref` не задан, можно передать `pr_url` (берётся head SHA из PR);
  - в UI `Auto` добавлен `Evaluate via GitHub` (repo/ref/required checks).
  - в UI `Auto` добавлена кнопка `Auto Next`:
    - для стадий `review/validation` автоматически запускает `evaluate/github` по `repo/ref` или `pr_url`;
  - добавлен server-side endpoint `auto-next`:
    - `POST /api/projects/{id}/autonomous/runs/{run_id}/auto-next`
    - централизует orchestration следующего шага на backend (без UI-логики принятия решения);
  - добавлен server-side endpoint run-level bounded orchestration:
    - `POST /api/projects/{id}/autonomous/runs/{run_id}/run-until-terminal`;
    - выполняет до `max_steps` тиков конкретного run до terminal state или до first wait/defer action;
    - защищён от conflict: если проектом владеет другой active run -> `409` (`active_run_id`, `requested_run_id`).
  - UI `Auto Next` переключен на backend endpoint `auto-next`.
  - добавлен управляемый fallback для `auto-next` при недоступном GitHub evaluate:
    - env `HIVE_AUTONOMOUS_AUTO_NEXT_FALLBACK` (`error` по умолчанию);
    - режим `manual_pending` (алиасы `manual`, `defer`) возвращает `202 deferred` + action `manual_evaluate_required`;
    - в run artifacts пишется observability event `auto_next_deferred`.
  - добавлен endpoint автодиспетчеризации следующей backlog-задачи:
    - `POST /api/projects/{id}/autonomous/dispatch-next`;
    - выбор задачи: highest priority (`critical>high>medium>low`) + FIFO по `created_at`;
    - guard от конфликтов: при существующем `queued|in_progress` run возвращает `409` с `active_run_id`.
  - добавлен fully server-driven endpoint:
    - `POST /api/projects/{id}/autonomous/execute-next`;
    - выбирает next `todo` задачу (priority+FIFO), создаёт run и в том же вызове прогоняет run через
      `run-until-terminal` (до `max_steps` / terminal / wait/defer action).
  - в Web UI (`Auto`) добавлена кнопка `Dispatch Next Todo` (server-driven старт следующей задачи).
  - добавлен orchestration endpoint одного autonomous тика:
    - `POST /api/projects/{id}/autonomous/loop/tick`;
    - поведение:
      - idle + todo backlog -> `dispatched_next_task`;
      - active `execution`:
        - если execution ещё активен -> `await_execution_stage_result`;
        - если найден terminal event по `execution_id` в `~/.hive/queen/session/{session_id}/events.jsonl`
          (`execution_completed|execution_failed|execution_paused`) -> stage auto-resolve через policy;
      - active `review/validation` -> авто-переход через GitHub checks (`source=loop_tick`) с поддержкой fallback policy.
  - cold-restart hardening для execution-stage resolve:
    - добавлен fallback по `worker_completed` (когда `execution_*` terminal event отсутствует);
    - если у последнего `worker_completed` `data.activations=[]`, execution помечается terminal
      даже при отсутствии live session object в памяти после рестарта;
    - исключён stale-loop сценарий `await_execution_stage_result` при фактически завершённом worker-run.
  - github evaluate repo/ref fallback hardening:
    - `backlog create` теперь подставляет `repository` из проекта при пустом task repository;
    - для auto-evaluate (`loop_tick`, `evaluate/github`, `auto-next`) добавлен fallback:
      `body -> task -> project.repository`, плюс нормализация GitHub URL/SSH в `owner/repo`;
    - `ref` берётся из `body/task`, а при отсутствии — из project execution template (`github.default_ref/default_branch`)
      или env default (`HIVE_AUTONOMOUS_GITHUB_DEFAULT_REF`, default `main`);
    - если передан `pr_url`, fallback `ref` не подставляется, чтобы сохранить приоритет PR-based resolution.
  - `no checks` policy control для GitHub evaluate:
    - новый execution template setting: `execution_template.github.no_checks_policy`;
    - поддерживаемые режимы: `error` (default), `manual_pending`, `success`;
    - env fallback: `HIVE_AUTONOMOUS_GITHUB_NO_CHECKS_POLICY`.
    - `success` позволяет не блокировать автономный цикл на репозиториях без check-runs;
      `manual_pending` возвращает deferred/manual-evaluate (`202`) без hard-fail.
  - добавлен global orchestration endpoint:
    - `POST /api/autonomous/loop/tick-all`;
    - выполняет server-side tick по выбранному списку `project_ids` (или по всем проектам), возвращает per-project status/action summary.
  - добавлен multi-step orchestration endpoint:
    - `POST /api/autonomous/loop/run-cycle`;
    - выполняет до `max_steps_per_project` тиков за один вызов (server-side), пока есть прогресс;
    - возвращает `steps[]` с action/status на каждом шаге;
    - добавлены terminal markers в per-project result:
      - `terminal`, `terminal_status`, `terminal_run_id`, `pr_ready` (из report `pr.ready`).
    - добавлены aggregate outcome counters в `summary.outcomes`
      (`completed|failed|escalated|manual_deferred|idle|in_progress|...`).
  - добавлен compact report endpoint:
    - `POST /api/autonomous/loop/run-cycle/report`;
    - возвращает ops-friendly сводку: `summary`, `projects[]`, `highlights` (`terminal_ready_projects`, `blocked_projects`, `manual_deferred_projects`, `top_risks`).
  - Telegram bridge интегрирован с autonomous compact report:
    - команда `/autodigest`;
    - inline action `show_autodigest` (`🧭 Auto Digest` в `/status` панели);
    - bridge вызывает `POST /api/autonomous/loop/run-cycle/report` и отправляет compact digest в чат.
  - добавлен proactive autonomous digest loop в Telegram bridge:
    - env `HIVE_TELEGRAM_AUTONOMOUS_DIGEST_ENABLED` (default enabled);
    - env `HIVE_TELEGRAM_AUTONOMOUS_DIGEST_HOUR` (default `12`);
    - daily anti-duplicate per chat + anti-noise gating (send only on risky outcomes).
  - в Web UI (`Auto`) добавлены кнопки:
    - `Loop Tick` (single-step)
    - `Run Cycle` (multi-step через backend `run-cycle`)
    - `Execute Next` (dispatch + run-until-terminal в одном backend call)
    - `Run Until Terminal` (для выбранного run).
  - в Web UI (`Auto`) добавлен `Ops / Loop Health` блок:
    - чтение `GET /api/autonomous/ops/status?project_id=<id>&include_runs=true`;
    - отображение `stuck_runs`, `no_progress_projects`, `loop_stale`, и `active_runs_visible`.
  - в Web UI (`Auto`) добавлен ручной `Refresh Ops` и визуальный stale indicator:
    - `loop_stale=true` подсвечивается warning-цветом;
    - оператор может обновлять ops snapshot независимо от общего `Refresh`.
  - в Web UI (`Auto`) добавлен `Execution Snapshot` блок для последних orchestration вызовов:
    - `source`, `action`, `terminal`, `terminal_status`, `steps_executed`, `run_id`, `updated_at`, `last_error`.
  - в Web UI (`Auto`) добавлен `Run Cycle Summary` блок:
    - показывает `summary.outcomes` counters;
    - показывает last-result поля (`outcome`, `terminal_status`, `pr_ready`, `steps_executed`).
  - Validation (April 9, 2026):
  - backend tests (container):
    - `uv run pytest framework/server/tests/test_api.py -k "tick_all" -q` -> `2 passed`;
    - `uv run pytest framework/server/tests/test_api.py -k "run_cycle_reports_terminal_and_pr_ready" -q` -> `1 passed`;
    - `uv run pytest framework/server/tests/test_api.py -k "run_cycle_report_endpoint or run_cycle_summary_outcomes or run_cycle_reports_terminal_and_pr_ready" -q` -> `3 passed`;
    - `uv run pytest framework/server/tests/test_api.py -k "run_cycle or tick_all or loop_tick or dispatch_next or autonomous or execution_template" -q` -> `36 passed`;
    - `uv run pytest framework/server/tests/test_telegram_bridge.py -q` -> `8 passed`;
  - frontend build: `npm run build` -> success (включая `Execute Next`, `Run Until Terminal`, `Ops / Loop Health` UI блоки);
  - runtime: `hive-core` status `healthy`;
  - live API smoke:
    - backlog create -> run create -> stage advance works;
    - `evaluate` endpoint updates stage via checks and applies retry policy;
    - `report` endpoint returns structured pipeline/checks output;
    - `evaluate/github` endpoint responds from GitHub API path (success/error surfaced explicitly);
    - `auto-next` endpoint responds with deterministic stage-gating errors/success.
  - conclusion:
    - item `15` done: pipeline закрывает сценарий `backlog -> execution -> review -> validation -> report/PR-ready`
      как через step-by-step endpoints, так и через server-driven orchestration (`execute-next` / `run-until-terminal`).
  - Validation (April 12, 2026 hotfix):
    - `uv run pytest core/framework/server/tests/test_api.py -k "terminal_worker_completed_without_execution_event or worker_completed_when_session_not_loaded or ignores_queen_active_stream" -q` -> `3 passed`;
    - `uv run pytest core/framework/server/tests/test_api.py -k "evaluate_github_no_checks_success_policy or auto_next_no_checks_manual_pending_policy" -q` -> `2 passed`;
    - live run `deep-research-smoke-20260412-005624/run_f0fd18ade1` после container restart:
      - execution auto-resolved из persisted events (`execution -> review`);
      - manual evaluate smoke (`review`, `validation`) завершил run в `completed`.
    - live smoke (`no-checks-success-smoke-2`):
      - project-level `execution_template.github.no_checks_policy=success`;
      - `auto-next` перешёл `review -> validation -> completed` без ручного checks input.
  - Validation (April 12, 2026 production run):
    - live autonomous task `n8n_redirect_fixer` выполнена end-to-end на реальном репозитории;
    - результат доставки изменений: merged PR #15
      (`https://github.com/salacoste/mcp-n8n-workflow-builder/pull/15`);
    - статус фикса в backlog: `done` (post-merge verification completed).

16. `P0` Operational Hardening (Limits/Observability/Backups/Runbooks)
- Status: `done`
- Scope:
  - лимиты и retry-политики на runtime, model/router и внешние MCP;
  - наблюдаемость: логи, базовые метрики, алерты на критичные деградации;
  - backup/restore для credential store и критичных runtime state;
  - финальные runbooks для оператора.
- Done when:
  - есть воспроизводимая эксплуатация с мониторингом и планом восстановления;
  - оператор может поддерживать систему без ручного дебага в коде.
- Progress:
  - добавлен autonomous ops observability endpoint:
    - `GET /api/autonomous/ops/status` (global summary + per-project task/run counters);
  - добавлен stuck-run alert в ops-status:
    - env `HIVE_AUTONOMOUS_STUCK_RUN_SECONDS` (default `1800`);
    - `alerts.stuck_runs_total`, `alerts.stuck_runs[]`, per-project `stuck_runs`/`max_stuck_for_seconds`;
  - `GET /api/autonomous/ops/status` поддерживает project scope filter:
    - query `project_id=<id>`;
    - summary содержит `project_filter` для явного observability контекста.
  - `GET /api/autonomous/ops/status` поддерживает run-level детали:
    - query `include_runs=true`;
    - response включает `active_runs[]` (`project_id`, `run_id`, `status`, `current_stage`, `no_progress_seconds`);
    - summary содержит `include_runs` flag.
  - добавлен ранний no-progress alert в ops-status:
    - env `HIVE_AUTONOMOUS_NO_PROGRESS_SECONDS` (default `900`);
    - `alerts.no_progress_projects_total`, `alerts.no_progress_projects[]` (active runs c устаревшим `updated_at`);
    - per-project: `active_runs`, `max_no_progress_seconds`.
  - добавлен loop heartbeat/state observability:
    - `scripts/autonomous_loop_tick.sh` пишет state в `~/.hive/server/autonomous_loop_state.json`
      (override: `HIVE_AUTONOMOUS_LOOP_STATE_PATH`);
    - `GET /api/autonomous/ops/status` читает loop state и отдает `loop{state_path,state,stale,...}`;
    - stale alert для loop heartbeat:
      - env `HIVE_AUTONOMOUS_LOOP_STALE_SECONDS` (default `600`);
      - `alerts.loop_stale`, `alerts.loop_stale_seconds`, `alerts.loop_stale_threshold_seconds`.
  - добавлен backup script состояния Hive:
    - `scripts/backup_hive_state.sh` (credentials/server/secrets/configuration snapshot + tar.gz);
  - добавлен restore script состояния Hive:
    - `scripts/restore_hive_state.sh` (safe restore + pre-restore snapshot + dry-run mode);
  - добавлен cron-friendly orchestration script:
    - `scripts/autonomous_loop_tick.sh` (project discovery + one tick per project + lock + summary);
  - добавлен operator health-check script для autonomous ops:
    - `scripts/autonomous_ops_health_check.sh`;
    - валидирует `stuck_runs`, `no_progress_projects`, `loop_stale` по настраиваемым лимитам;
    - поддерживает project scope (`HIVE_AUTONOMOUS_HEALTH_PROJECT_ID`).
  - добавлен unified ops drill script:
    - `scripts/autonomous_ops_drill.sh`;
    - выполняет shell syntax checks, ops health gate, backup, restore dry-run, и optional loop smoke;
    - поддерживает offline-friendly режим через `HIVE_AUTONOMOUS_DRILL_SKIP_NETWORK=true`;
    - loop smoke по умолчанию scoped на `default` (`HIVE_AUTONOMOUS_DRILL_PROJECT_IDS` override).
  - добавлены macOS launchd wrappers для автономного цикла:
    - `scripts/install_autonomous_loop_launchd.sh`
    - `scripts/status_autonomous_loop_launchd.sh`
    - `scripts/uninstall_autonomous_loop_launchd.sh`;
  - `scripts/autonomous_loop_tick.sh` обновлён на server-side global tick режим:
    - по умолчанию использует `POST /api/autonomous/loop/run-cycle` (multi-step);
    - fallback: `run-cycle` -> `tick-all` -> per-project `loop/tick`;
    - env toggle: `HIVE_AUTONOMOUS_USE_TICK_ALL=true|false`.
    - env tuning: `HIVE_AUTONOMOUS_MAX_STEPS_PER_PROJECT` (default `3`).
  - обновлён локальный runbook (`docs/LOCAL_PROD_RUNBOOK.md`) с командами ops-status и backup.
- Validation (April 9, 2026):
  - backend tests (container): `uv run pytest framework/server/tests/test_api.py -k "autonomous or execution_template" -q` -> `36 passed`;
  - targeted stuck-alert tests:
    - `uv run pytest framework/server/tests/test_api.py -k "autonomous_ops_status" -q` -> `7 passed`;
  - run-level bounded orchestration tests:
    - `uv run pytest framework/server/tests/test_api.py -k "run_until_terminal or autonomous or execution_template" -q` -> `36 passed`;
  - project-level execute-next orchestration tests:
    - `uv run pytest framework/server/tests/test_api.py -k "execute_next or run_until_terminal or autonomous or execution_template" -q` -> `36 passed`;
  - live ops endpoint: `GET /api/autonomous/ops/status` -> `status: ok` + агрегированные counters;
  - backup drill: `./scripts/backup_hive_state.sh` -> archive created under `~/.hive/backups/`;
  - restore drill: `./scripts/restore_hive_state.sh --archive <latest> --dry-run` -> restore plan produced, no writes in dry-run;
  - autonomous loop smoke:
    - `HIVE_AUTONOMOUS_PROJECT_IDS=default HIVE_AUTONOMOUS_USE_RUN_CYCLE=true HIVE_AUTONOMOUS_USE_TICK_ALL=true ./scripts/autonomous_loop_tick.sh` -> `ok=1 deferred=0 failed=0`;
  - compact report smoke:
    - `POST /api/autonomous/loop/run-cycle/report` (`project_ids=["default"]`) -> `status=ok`, `summary.outcomes` and `highlights` populated.
  - telegram bridge smoke:
    - bridge container restart -> `healthy`;
    - команды `/autodigest` и callback `show_autodigest` покрыты unit-тестами;
    - proactive anti-noise поведение покрыто unit-тестом (`no risky outcomes -> no send`).
  - launchd scripts lint/status:
    - `bash -n scripts/autonomous_loop_tick.sh scripts/autonomous_ops_health_check.sh scripts/autonomous_ops_drill.sh scripts/install_autonomous_loop_launchd.sh scripts/status_autonomous_loop_launchd.sh scripts/uninstall_autonomous_loop_launchd.sh` -> `ok`;
    - `./scripts/status_autonomous_loop_launchd.sh` -> `not-installed` (ожидаемо на чистой машине);
  - frontend build: `npm run build` -> success.
  - ops drill (local):
    - `HIVE_AUTONOMOUS_DRILL_SKIP_NETWORK=true HIVE_AUTONOMOUS_DRILL_SKIP_LOOP_SMOKE=true ./scripts/autonomous_ops_drill.sh` -> `ok=3 failed=0`.
  - ops drill (full, scoped):
    - `./scripts/autonomous_ops_drill.sh` -> `ok=5 failed=0`.
  - conclusion:
    - item `16` done: наблюдаемость, health gates, backup/restore drills, loop heartbeat monitoring, и operator runbooks
      формализованы и воспроизводимы.

## Execution Wave 2 (next)

17. `P0` Runtime Parity Verification (Container vs Local Code)
- Status: `done`
- Scope:
  - сравнить API contract и runtime behavior между локальным кодом и `hive-core` контейнером;
  - устранить deployment drift (пример: `/api/autonomous/ops/status` в контейнере без `alerts/loop` полей);
  - зафиксировать reproducible deploy/restart шаги для parity.
- Done when:
  - контракт ключевых endpoint одинаков локально и в контейнере;
  - drift check проходит автоматически.
- Progress:
  - добавлен runtime parity check script: `scripts/check_runtime_parity.sh`;
  - script валидирует JSON/contract для:
    - `GET /api/autonomous/ops/status?project_id=...&include_runs=true`
    - `POST /api/autonomous/loop/run-cycle/report`;
  - drift устранён через rebuild/redeploy `hive-core` из текущего repo state;
  - parity check интегрирован в preflight script `scripts/local_prod_checklist.sh` как обязательный gate;
  - live validation: `./scripts/check_runtime_parity.sh` -> `runtime parity check passed`.

18. `P0` Telegram Bridge Single-Consumer Hardening
- Status: `done`
- Scope:
  - устранить `getUpdates 409 Conflict` (гарантия single poller instance);
  - добавить startup guard/lock и явный health signal по Telegram bridge;
  - добавить operator guide для webhook/polling mode switching.
- Done when:
  - в steady-state нет recurring `409 Conflict` в логах;
  - bridge mode и ownership понятны и воспроизводимы.
- Progress:
  - добавлен single-consumer filesystem lock для polling bridge:
    - `HIVE_TELEGRAM_SINGLE_CONSUMER` (default enabled),
    - `HIVE_TELEGRAM_POLL_LOCK_PATH` (default `~/.hive/server/telegram-poll.lock`);
  - добавлен bridge mode contract:
    - `HIVE_TELEGRAM_MODE` (поддерживаемый runtime: `polling`);
    - неподдерживаемый mode не стартует polling и возвращает явный startup status;
  - добавлен observability endpoint:
    - `GET /api/telegram/bridge/status` (`mode`, `poller_owner`, `running`, `startup_status`, `last_poll_error`);
  - `/api/health` теперь включает `telegram_bridge` status snapshot;
  - обновлён runbook `LOCAL_PROD_RUNBOOK.md` с operator guide по mode/ownership switching.
- Validation (April 9, 2026):
  - tests:
    - `uv run --active pytest core/framework/server/tests/test_telegram_bridge.py -q` -> `9 passed`;
    - `uv run --active pytest core/framework/server/tests/test_api.py -k "health or telegram_bridge_status_endpoint" -q` -> `2 passed`;
  - live runtime:
    - `GET /api/telegram/bridge/status` -> `status=ok`, `poller_owner=true`, `running=true`;
    - `GET /api/health` содержит `telegram_bridge` status;
    - logs: `docker compose logs --since=5m hive-core | rg "Conflict|409|getUpdates"` -> no recurring matches.

19. `P1` Frontend Performance Hardening (Workspace)
- Status: `done`
- Scope:
  - снизить размер основных JS chunks (`vite` warning >500kB);
  - внедрить code-splitting для heavy modal/control-center блоков;
  - подтвердить улучшение build artifacts и загрузки.
- Done when:
  - нет критичных bundle warnings или есть документированное обоснование;
  - baseline/perf report добавлен в runbook.
- Progress:
  - добавлен `rollupOptions.output.manualChunks` в `core/frontend/vite.config.ts`;
  - выделен `vendor` chunk для зависимостей из `node_modules`, снижена масса entry chunk.
- Validation (April 9, 2026):
  - baseline build:
    - `dist/assets/index-*.js` = `612.10 kB` (warning >500 kB);
  - after hardening:
    - `dist/assets/index-*.js` = `223.81 kB`;
    - `dist/assets/vendor-*.js` = `387.46 kB`;
    - warnings отсутствуют;
  - command:
    - `cd core/frontend && npm run build` -> success.

20. `P1` Autonomous Loop SLOs and Alert Policies
- Status: `done`
- Scope:
  - формализовать SLO/threshold policy для stuck/no-progress/loop-stale;
  - добавить alert profiles для `dev/local` и `prod`;
  - закрепить periodic drill cadence и acceptance criteria.
- Done when:
  - policy и thresholds задокументированы и применяются скриптами health/drill;
  - операторский runbook включает регулярный SLO review cycle.
- Progress:
  - `scripts/autonomous_ops_health_check.sh` расширен profile-driven thresholds:
    - `HIVE_AUTONOMOUS_HEALTH_PROFILE=local|dev|staging|prod`;
    - explicit env overrides по-прежнему имеют приоритет;
  - добавлен SLO policy документ:
    - `docs/ops/autonomous-slo-policy.md` (thresholds, profiles, drill cadence, acceptance criteria);
  - runbook обновлён profile-командами health-check и ссылкой на SLO policy.
- Validation (April 9, 2026):
  - syntax: `bash -n scripts/autonomous_ops_health_check.sh` -> ok;
  - runtime execution:
    - `HIVE_AUTONOMOUS_HEALTH_PROFILE=local ./scripts/autonomous_ops_health_check.sh` -> fail (expected due active backlog risk);
    - `HIVE_AUTONOMOUS_HEALTH_PROFILE=prod ./scripts/autonomous_ops_health_check.sh` -> fail (strict prod gate);
  - conclusion:
    - policy gates работают и корректно выявляют текущие риски (`stuck_runs`, `no_progress_projects`).

## Execution Wave 3 (next)

21. `P0` Stale Run Remediation Controls (safe bulk ops)
- Status: `done`
- Scope:
  - добавить безопасный bulk-remediation stale run'ов (`queued|in_progress`) через API;
  - поддержать `dry_run` по умолчанию и явное подтверждение для apply-режима;
  - добавить операторский CLI-скрипт и runbook инструкции.
- Done when:
  - оператор видит кандидатов stale run'ов без записи (preview);
  - apply режим переводит stale run'ы в terminal status контролируемо и воспроизводимо.
- Progress:
  - добавлен endpoint:
    - `POST /api/autonomous/ops/remediate-stale`;
    - параметры: `project_id`, `older_than_seconds`, `max_runs`, `dry_run`, `confirm`, `action`, `reason`;
    - `action` поддерживает: `failed|escalated`;
    - `dry_run=true` default; `confirm=true` обязателен при `dry_run=false`.
  - apply flow:
    - stale `queued|in_progress` run переводится в terminal status;
    - в artifacts добавляется `ops_remediation` event;
    - связанный task в `in_progress` переводится в `blocked`.
  - добавлен скрипт:
    - `scripts/autonomous_remediate_stale_runs.sh`.
  - runbook обновлён командами remediation API/CLI.
- Validation (April 9, 2026):
  - tests:
    - `uv run --active pytest core/framework/server/tests/test_api.py -k "autonomous_ops_remediate_stale or autonomous_ops_status" -q` -> `9 passed`;
  - script lint:
    - `bash -n scripts/autonomous_remediate_stale_runs.sh` -> ok;
  - live dry-run:
    - `POST /api/autonomous/ops/remediate-stale` (`project_id=default`) -> `candidates_total=6`, `selected_total=5`, `remediated_total=0`;
    - `./scripts/autonomous_remediate_stale_runs.sh` -> returns full candidate list (`dry_run=true`).

22. `P0` Controlled Remediation Rollout (project-scoped apply)
- Status: `done`
- Scope:
  - выполнить apply remediation по конкретным project scopes;
  - сверить post-remediation ops status (`stuck_runs_total`, `no_progress_projects_total`);
  - закрепить safe operating sequence в runbook.
- Progress:
  - выполнен apply remediation для `project_id=default`:
    - `dry_run=false`, `confirm=true`, `action=escalated`, `older_than_seconds=1800`;
    - remediated `6/6` stale active runs.
  - post-remediation верификация:
    - `/api/autonomous/ops/status?project_id=default&include_runs=true`:
      - `stuck_runs_total=0`,
      - `no_progress_projects_total=0`,
      - `active_runs=0`,
      - `runs_by_status.escalated=6`.
  - profile health gate:
    - `HIVE_AUTONOMOUS_HEALTH_PROJECT_ID=default HIVE_AUTONOMOUS_HEALTH_PROFILE=prod ./scripts/autonomous_ops_health_check.sh` -> `passed`.

23. `P1` Build Path Optimization (Docker rebuild latency)
- Status: `done`
- Scope:
  - сократить время локальных rebuild (кэширование/слои/optional Playwright deps path);
  - определить быстрый dev rebuild path и production rebuild path;
  - задокументировать trade-offs и рекомендованные команды.
- Progress:
  - Dockerfile обновлён build arg:
    - `ARG HIVE_DOCKER_INSTALL_PLAYWRIGHT=1`;
    - при `0` пропускается тяжелый `playwright install --with-deps`.
  - docker-compose build args обновлён:
    - `HIVE_DOCKER_INSTALL_PLAYWRIGHT: ${HIVE_DOCKER_INSTALL_PLAYWRIGHT:-1}`.
  - runbook обновлён командами:
    - fast local rebuild: `HIVE_DOCKER_INSTALL_PLAYWRIGHT=0 docker compose up -d --build hive-core`;
    - full/prod rebuild: `HIVE_DOCKER_INSTALL_PLAYWRIGHT=1 ...`.
- Validation (April 9, 2026):
  - `HIVE_DOCKER_INSTALL_PLAYWRIGHT=0 docker compose build hive-core`:
    - build log подтверждает skip:
      `Skipping Playwright install in Docker image (HIVE_DOCKER_INSTALL_PLAYWRIGHT=0)`;
    - heavy browser dependency step исключён из fast path.

## Execution Wave 4 (in progress)

24. `P0` Backlog Governance Automation
- Status: `done`
- Scope:
  - добавить автоматическую валидацию backlog markdown (ID/status consistency);
  - закрепить правило: работа идёт только из backlog, через явный `Current Focus`;
  - добавить operator command для быстрого sanity-check перед продолжением волны.
- Done when:
  - есть reproducible validator и команда запуска;
  - validator ловит structural ошибки task lifecycle.
- Progress:
  - добавлен validator script:
    - `scripts/validate_backlog_markdown.py`;
  - validator checks:
    - task id uniqueness/contiguity;
    - allowed status set (`todo|in_progress|blocked|done`);
    - наличие status строки рядом с task entry;
    - не более одного `in_progress` task;
    - `Current Focus` references только на существующие task ids.
- Validation (April 9, 2026):
  - `uv run python scripts/validate_backlog_markdown.py` -> `[ok] backlog validation passed`;
  - output: `tasks_total=28`, `in_progress=[]`, `focus_refs=[25,26]`.

25. `P0` MCP Credential Profile Normalization
- Status: `done`
- Scope:
  - нормализовать `local_pro_stack` credential expectations под фактически используемые MCP;
  - убрать noise/warn-only дыры для неиспользуемых Google integrations;
  - зафиксировать profile policy (required vs optional keys).
- Progress:
  - `scripts/audit_mcp_credentials.py` обновлён:
    - bundle структура: `required` + `optional`;
    - `local_pro_stack` required оставлены только для реально блокирующего local runtime;
    - Google extended keys переведены в optional non-blocking группу.
  - output audit теперь разделяет:
    - `Missing` (blocking required);
    - `Optional missing` (non-blocking).
- Validation (April 9, 2026):
  - `uv run python scripts/audit_mcp_credentials.py --bundle local_pro_stack`:
    - `Missing: 0`, `Optional missing: 3`;
  - `./scripts/local_prod_checklist.sh`:
    - `[OK] local_pro_stack credentials complete` (без ложного warning).

26. `P1` Ops UI: Stale Remediation Control Center
- Status: `done`
- Scope:
  - добавить в Web UI блок для `ops/remediate-stale` (preview/apply + confirm);
  - показать remediation preview/result в модале `Auto`.
- Progress:
  - frontend API расширен:
    - `autonomousApi.remediateStaleRuns(...)` + typed response `AutonomousRemediateStaleResponse`;
  - в `workspace` (`Auto` modal) добавлен блок `Stale Remediation`:
    - action selector (`escalated|failed`);
    - inputs `older_than_seconds`, `max_runs`;
    - `Preview` (dry-run) и `Apply` (with confirm);
    - result summary (`selected/remediated`).
- Validation (April 9, 2026):
  - frontend build:
    - `cd core/frontend && npm run build` -> success.

27. `P1` Dev/Prod Compose Profiles
- Status: `done`
- Scope:
  - разделить local-fast и prod-full paths через compose profiles/override;
  - закрепить команды и ограничения (web_scrape availability).
- Progress:
  - Docker build path параметризован через
    `HIVE_DOCKER_INSTALL_PLAYWRIGHT` (`0/1`);
  - compose build args прокинут в `hive-core`;
  - runbook дополнен fast/prod командами и ограничениями.
- Validation (April 9, 2026):
  - `HIVE_DOCKER_INSTALL_PLAYWRIGHT=0 docker compose build hive-core` -> success;
  - build log содержит skip marker для Playwright deps.

28. `P1` Autonomous Factory Acceptance Suite
- Status: `done`
- Scope:
  - собрать единый acceptance flow:
    - parity -> health -> remediation dry-run -> telegram status -> run-cycle report;
  - оформить one-command smoke gate для операторского daily use.
- Progress:
  - добавлен one-command gate script:
    - `scripts/autonomous_acceptance_gate.sh`;
  - gate checks:
    - backlog validator;
    - runtime parity;
    - per-project prod health gate;
    - stale remediation dry-run;
    - run-cycle compact report;
    - telegram bridge status;
    - optional local prod checklist (skip toggle).
- Validation (April 9, 2026):
  - syntax:
    - `bash -n scripts/autonomous_acceptance_gate.sh` -> ok;
  - runtime smoke:
    - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true ./scripts/autonomous_acceptance_gate.sh` -> `ok=6 failed=0`.

## Execution Wave 5 (in progress)

29. `P0` Strict Backlog Execution Lock
- Status: `done`
- Scope:
  - ужесточить backlog validator, чтобы пустой `Current Focus` и отсутствие `in_progress` считались ошибкой;
  - гарантировать ссылку `Current Focus` -> активная задача.
- Progress:
  - `scripts/validate_backlog_markdown.py` обновлён:
    - `Current Focus` обязателен (по умолчанию);
    - минимум одна `in_progress` задача обязательна (по умолчанию);
    - `in_progress` должна быть отражена в `Current Focus`;
    - добавлены env toggles: `HIVE_BACKLOG_REQUIRE_FOCUS`, `HIVE_BACKLOG_REQUIRE_IN_PROGRESS`.
- Validation (April 9, 2026):
  - `uv run python scripts/validate_backlog_markdown.py` -> passed with strict mode defaults.

30. `P1` Backlog Status CLI Summary
- Status: `done`
- Scope:
  - добавить CLI summary текущего backlog: active focus, in-progress item, статус-счетчики;
  - использовать его в ежедневном operator цикле.
- Progress:
  - добавлен script:
    - `scripts/backlog_status.py`;
  - script выводит:
    - `tasks_total`,
    - `status_counts`,
    - `in_progress`,
    - `focus_refs`,
    - детальный список focus items (priority/status/title).
- Validation (April 9, 2026):
  - `uv run python scripts/backlog_status.py` -> success;
  - `uv run python scripts/validate_backlog_markdown.py` -> success.

31. `P1` Operator UI/Runbook Sync Check
- Status: `done`
- Scope:
  - добавить проверку согласованности runbook команд и фактических скриптов;
  - зафиксировать в acceptance gate (non-destructive mode).
- Progress:
  - добавлен script:
    - `scripts/check_runbook_sync.py`;
  - проверка включена в acceptance gate:
    - `scripts/autonomous_acceptance_gate.sh` (`runbook sync check` step).
- Validation (April 9, 2026):
  - `uv run python scripts/check_runbook_sync.py` -> `[ok] all referenced scripts exist` (`script_refs=22`);
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true ./scripts/autonomous_acceptance_gate.sh` -> `ok=7 failed=0`.

32. `P1` Backlog Archive Hygiene
- Status: `done`
- Scope:
  - добавить процесс архивации старых closed-wave пунктов в отдельный документ;
  - держать основной backlog компактным и операционным.
- Progress:
  - добавлен archive snapshot script:
    - `scripts/backlog_archive_snapshot.py`;
  - snapshot pipeline:
    - читает текущий backlog,
    - выгружает все `done` задачи в отдельный markdown snapshot в `docs/autonomous-factory/archive/`.
  - добавлен archive hygiene script:
    - `scripts/backlog_archive_hygiene.py`;
  - script создаёт/обновляет `docs/autonomous-factory/archive/INDEX.md`;
  - поддерживается безопасный prune режим (`--prune-keep N --yes`).
- Validation (April 9, 2026):
  - `uv run python scripts/backlog_archive_snapshot.py` -> success;
  - snapshot создан:
    - `docs/autonomous-factory/archive/backlog-done-snapshot-20260409-165752.md`.
  - `uv run python scripts/backlog_archive_hygiene.py` -> success;
  - archive index создан:
    - `docs/autonomous-factory/archive/INDEX.md`.

## Execution Wave 6 (in progress)

33. `P1` Acceptance Gate Scheduler
- Status: `done`
- Scope:
  - добавить scheduler wrappers для регулярного запуска `autonomous_acceptance_gate.sh`;
  - использовать уже принятый launchd pattern (install/status/uninstall).
- Progress:
  - добавлены launchd wrappers:
    - `scripts/install_acceptance_gate_launchd.sh`
    - `scripts/status_acceptance_gate_launchd.sh`
    - `scripts/uninstall_acceptance_gate_launchd.sh`;
  - install script поддерживает `HIVE_ACCEPTANCE_GATE_INTERVAL` (default `3600`, min `300`);
  - runbook дополнен acceptance scheduler командами.
- Validation (April 9, 2026):
  - syntax:
    - `bash -n scripts/install_acceptance_gate_launchd.sh scripts/status_acceptance_gate_launchd.sh scripts/uninstall_acceptance_gate_launchd.sh` -> ok;
  - status check:
    - `./scripts/status_acceptance_gate_launchd.sh` -> `not-installed` (expected on clean setup).

34. `P1` Acceptance Report Artifacts
- Status: `done`
- Scope:
  - сохранять краткий acceptance report artifact (timestamp + status summary);
  - добавить ссылку на artifact в operator runbook.
- Progress:
  - добавлен artifact generator:
    - `scripts/acceptance_report_artifact.py`;
  - artifacts пишутся в:
    - `docs/ops/acceptance-reports/acceptance-report-<timestamp>.json`
    - `docs/ops/acceptance-reports/latest.json`;
  - шаг artifact generation встроен в:
    - `scripts/autonomous_acceptance_gate.sh`.
- Validation (April 9, 2026):
  - `uv run python scripts/acceptance_report_artifact.py` -> success;
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true ./scripts/autonomous_acceptance_gate.sh` -> `ok=9 failed=0`;
  - подтвержден artifact:
    - `docs/ops/acceptance-reports/acceptance-report-20260409-171907.json`.

35. `P2` Backlog Archive Rotation Policy
- Status: `done`
- Scope:
  - определить и зафиксировать политику ротации snapshot'ов (keep N, cadence);
  - синхронизировать policy с `backlog_archive_hygiene.py`.
- Progress:
  - добавлен policy doc:
    - `docs/autonomous-factory/archive/ROTATION_POLICY.md`;
  - runbook обновлён командами:
    - `backlog_archive_snapshot.py` + `backlog_archive_hygiene.py`;
  - политика retention:
    - keep latest `20` snapshots;
    - prune только с `--yes`.
- Validation (April 9, 2026):
  - `uv run python scripts/backlog_archive_hygiene.py` -> success;
  - acceptance gate green:
    - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true ./scripts/autonomous_acceptance_gate.sh` -> `ok=9 failed=0`.

## Execution Wave 7 (in progress)

36. `P1` Scheduled Acceptance Rollout Runbook
- Status: `done`
- Scope:
  - формализовать rollout шаги включения acceptance scheduler в local/ops routine;
  - добавить troubleshooting примеры для scheduler logs.
- Progress:
  - `docs/LOCAL_PROD_RUNBOOK.md` расширен:
    - rollout sequence для acceptance scheduler;
    - команды мониторинга `.logs/acceptance-gate.out.log/.err.log`;
    - troubleshooting notes для типовых отказов.
- Validation (April 9, 2026):
  - syntax:
    - `bash -n scripts/install_acceptance_gate_launchd.sh scripts/status_acceptance_gate_launchd.sh scripts/uninstall_acceptance_gate_launchd.sh` -> `ok`;
  - runtime check:
    - `./scripts/status_acceptance_gate_launchd.sh` -> `not-installed` (ожидаемо до явного rollout install).

37. `P1` Archive Prune Automation Guardrails
- Status: `done`
- Scope:
  - добавить safe guardrails вокруг prune режима (preview before delete);
  - документировать recovery path для ошибочного prune.
- Progress:
  - `scripts/backlog_archive_hygiene.py` расширен guardrails:
    - preview списка кандидатов на prune даже без `--yes`;
    - `prune_candidates` + ограничение вывода через `--max-preview`;
    - явный dry-run marker и recovery hint в output.
  - обновлён `docs/autonomous-factory/archive/ROTATION_POLICY.md`:
    - двухшаговый flow `preview -> apply`;
    - recovery path (`git restore` + index rebuild + snapshot regenerate).
  - обновлён `docs/LOCAL_PROD_RUNBOOK.md`:
    - operator-команды для prune preview/apply;
    - recovery блок после accidental prune.
- Validation (April 9, 2026):
  - `uv run python scripts/backlog_archive_hygiene.py --prune-keep 20` -> `ok`, non-destructive preview mode;
  - `uv run python scripts/validate_backlog_markdown.py` -> `ok`.

38. `P2` Backlog Compaction Checklist
- Status: `done`
- Scope:
  - добавить checklist для периодической компактификации backlog;
  - закрепить cadence в operator workflow.
- Progress:
  - добавлен документ:
    - `docs/autonomous-factory/BACKLOG_COMPACTION_CHECKLIST.md`;
  - checklist покрывает cadence, archive hygiene steps, prune guardrails и exit criteria.
- Validation (April 9, 2026):
  - `uv run python scripts/validate_backlog_markdown.py` -> `ok`;
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true ./scripts/autonomous_acceptance_gate.sh` -> `ok=9 failed=0`.

## Execution Wave 8 (in progress)

39. `P1` Acceptance Artifact Lifecycle Automation
- Status: `done`
- Scope:
  - автоматизировать ротацию и компактное хранение `docs/ops/acceptance-reports/*`;
  - добавить guardrails (preview + explicit apply) по аналогии с archive prune;
  - включить шаг в operator routine/runbook.
- Progress:
  - добавлен script:
    - `scripts/acceptance_report_hygiene.py`;
  - реализован guardrail flow для lifecycle:
    - preview candidates без удаления (`--keep N`);
    - apply только с явным `--yes`;
    - `--max-preview` для контролируемого вывода кандидатов.
  - runbook обновлён:
    - команда maintenance `uv run python scripts/acceptance_report_hygiene.py --keep 50`;
    - шаг добавлен в acceptance scheduler rollout и preflight routine.
- Validation (April 9, 2026):
  - `uv run python scripts/acceptance_report_hygiene.py --keep 50` -> `ok`, non-destructive preview mode;
  - `uv run python scripts/check_runbook_sync.py` -> `ok`, script_refs include `acceptance_report_hygiene.py`;
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true ./scripts/autonomous_acceptance_gate.sh` -> `ok=9 failed=0`.
  - `scripts/autonomous_acceptance_gate.sh` интегрирован с report lifecycle:
    - preview hygiene step по умолчанию;
    - apply режим через `HIVE_ACCEPTANCE_REPORT_PRUNE_APPLY=true`.

40. `P2` Acceptance Trend Digest Baseline
- Status: `done`
- Scope:
  - добавить baseline digest по acceptance artifacts (recent pass/fail counters);
  - упростить операторский weekly review состояния quality gates.
- Progress:
  - добавлен script:
    - `scripts/acceptance_report_digest.py`;
  - digest summary включает:
    - lookback window (`--days`),
    - total/pass/fail counters,
    - recent artifact lines с `health/ops/telegram` статусами и PASS/FAIL marker;
  - runbook обновлён weekly-командой:
    - `uv run python scripts/acceptance_report_digest.py --days 7 --limit 20`.
- Validation (April 9, 2026):
  - `uv run python scripts/acceptance_report_digest.py --days 7 --limit 20` -> `pass=6 fail=0`;
  - `uv run python scripts/check_runbook_sync.py` -> `ok`, `script_refs=28`.

41. `P2` Acceptance Digest Artifact Export
- Status: `done`
- Scope:
  - добавить опцию экспорта digest в JSON/markdown артефакт для weekly review;
  - унифицировать хранение с `docs/ops/acceptance-reports/`.
- Progress:
  - `scripts/acceptance_report_digest.py` расширен export опциями:
    - `--out-json <path>`
    - `--out-md <path>`;
  - сформированы digest artifacts:
    - `docs/ops/acceptance-reports/digest-latest.json`
    - `docs/ops/acceptance-reports/digest-latest.md`;
  - runbook дополнен командой weekly digest export.
- Validation (April 9, 2026):
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true ./scripts/autonomous_acceptance_gate.sh` включает шаг
    `acceptance report digest artifact` и генерирует `digest-latest.json/.md`;
  - gate result: `ok=11 failed=0`.

42. `P1` Acceptance Historical Regression Policy
- Status: `done`
- Scope:
  - добавить enforceable historical guard по acceptance artifacts (не только digest);
  - подключить optional strict policy в acceptance gate через env knobs.
- Progress:
  - добавлен script:
    - `scripts/acceptance_report_regression_guard.py`;
  - поддерживаются thresholds:
    - `--days`, `--max-fail`, `--min-pass-rate`, `--allow-empty`;
  - acceptance gate расширен env policy knobs:
    - `HIVE_ACCEPTANCE_ENFORCE_HISTORY`
    - `HIVE_ACCEPTANCE_HISTORY_MAX_FAIL`
    - `HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE`;
  - runbook дополнен policy knobs и manual command.
- Validation (April 9, 2026):
  - `uv run python scripts/acceptance_report_regression_guard.py --days 7 --max-fail 0 --min-pass-rate 1.0` -> `ok`;
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true HIVE_ACCEPTANCE_ENFORCE_HISTORY=true ./scripts/autonomous_acceptance_gate.sh` -> `ok=12 failed=0`.

43. `P2` Acceptance Scheduler Profile Presets
- Status: `done`
- Scope:
  - добавить profile presets для acceptance scheduler (balanced/strict) без ручного подбора env;
  - ускорить и стандартизировать rollout для local operator routine.
- Progress:
  - `scripts/install_acceptance_gate_launchd.sh` расширен preset profiles:
    - `HIVE_ACCEPTANCE_PROFILE=balanced|strict`;
  - defaults профилей централизованы с возможностью env overrides;
  - `scripts/status_acceptance_gate_launchd.sh` теперь показывает ключевые env (включая profile и history guard);
  - runbook обновлён preset-примерами запуска scheduler.
- Validation (April 9, 2026):
  - `bash -n scripts/install_acceptance_gate_launchd.sh scripts/status_acceptance_gate_launchd.sh` -> `ok`;
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true HIVE_ACCEPTANCE_ENFORCE_HISTORY=true ./scripts/autonomous_acceptance_gate.sh` -> `ok=12 failed=0`.

44. `P2` Weekly Maintenance Scheduler Wrappers
- Status: `done`
- Scope:
  - добавить one-command weekly maintenance routine для acceptance artifacts/digest/guard;
  - подготовить дальнейшую автоматизацию weekly cadence.
- Progress:
  - добавлен script:
    - `scripts/acceptance_weekly_maintenance.sh`;
  - script объединяет digest export + hygiene + regression guard.
  - добавлены macOS launchd wrappers:
    - `scripts/install_acceptance_weekly_launchd.sh`
    - `scripts/status_acceptance_weekly_launchd.sh`
    - `scripts/uninstall_acceptance_weekly_launchd.sh`;
  - runbook дополнён weekly scheduler командами.
- Validation (April 9, 2026):
  - `bash -n scripts/acceptance_weekly_maintenance.sh scripts/install_acceptance_weekly_launchd.sh scripts/status_acceptance_weekly_launchd.sh scripts/uninstall_acceptance_weekly_launchd.sh` -> `ok`;
  - `./scripts/acceptance_weekly_maintenance.sh` -> `ok=3 failed=0`;
  - `uv run python scripts/check_runbook_sync.py` -> `ok`, `script_refs=32`.

45. `P2` Acceptance Maintenance Ops Summary Command
- Status: `done`
- Scope:
  - добавить compact ops summary для acceptance maintenance (last artifact + digest counters + guard status);
  - использовать summary как быстрый операторский snapshot без запуска полного gate.
- Progress:
  - добавлен script:
    - `scripts/acceptance_ops_summary.py`;
  - поддержаны форматы:
    - human-readable summary;
    - JSON (`--json`).
  - acceptance gate расширен summary step:
    - `acceptance ops summary`;
    - `HIVE_ACCEPTANCE_SUMMARY_JSON=true` для JSON mode.
  - runbook дополнен командами `acceptance_ops_summary.py`.
- Validation (April 9, 2026):
  - `uv run python scripts/acceptance_ops_summary.py` -> `summary available`;
  - `uv run python scripts/acceptance_ops_summary.py --json` -> valid JSON snapshot;
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true HIVE_ACCEPTANCE_ENFORCE_HISTORY=true HIVE_ACCEPTANCE_SUMMARY_JSON=true ./scripts/autonomous_acceptance_gate.sh` -> `ok=13 failed=0`.

46. `P2` Acceptance Scheduler Observability Snapshot
- Status: `done`
- Scope:
  - добавить operator-команду для быстрых статус-снапшотов launchd schedulers (hourly gate + weekly maintenance);
  - сократить время диагностики scheduler state без ручного `launchctl` разбирательства.
- Progress:
  - task и focus созданы; implementation in progress.
  - добавлен snapshot script:
    - `scripts/acceptance_scheduler_snapshot.sh`;
  - snapshot включает:
    - hourly/weekly launchd status;
    - последние хвосты логов acceptance-gate/acceptance-weekly.
  - runbook дополнен командой snapshot.
- Validation (April 9, 2026):
  - `bash -n scripts/acceptance_scheduler_snapshot.sh` -> `ok`;
  - `HIVE_ACCEPTANCE_SNAPSHOT_TAIL_LINES=5 ./scripts/acceptance_scheduler_snapshot.sh` -> `ok` (not-installed state surfaced explicitly).

47. `P1` Runbook Sync Parser Hardening
- Status: `done`
- Scope:
  - устранить пропуски script refs в `check_runbook_sync.py` (включая uninstall команды);
  - повысить надёжность extract logic для line-based runbook commands.
- Progress:
  - `scripts/check_runbook_sync.py` переведён на line-based extraction (`_extract_refs`);
  - regex extraction упростён и стабилизирован для `./scripts/...` и `scripts/...` паттернов;
  - подтверждено обнаружение ранее пропускавшихся refs:
    - `scripts/uninstall_acceptance_gate_launchd.sh`
    - `scripts/uninstall_acceptance_weekly_launchd.sh`.
- Validation (April 9, 2026):
  - `uv run python scripts/check_runbook_sync.py` -> `script_refs=37` и включает `uninstall_acceptance_*`;
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true HIVE_ACCEPTANCE_ENFORCE_HISTORY=true HIVE_ACCEPTANCE_SUMMARY_JSON=true ./scripts/autonomous_acceptance_gate.sh` -> `ok=13 failed=0`.

48. `P2` Runbook Sync Extractor Test Coverage
- Status: `done`
- Scope:
  - добавить автотесты для extractor logic в `check_runbook_sync.py`;
  - зафиксировать кейсы `install/status/uninstall`, inline и code block команды.
- Progress:
  - добавлен test module:
    - `scripts/tests/test_check_runbook_sync.py`;
  - покрыты кейсы:
    - mixed lines (`install/status/uninstall`);
    - inline command extraction;
    - dedup behavior.
- Validation (April 9, 2026):
  - `uv run pytest scripts/tests/test_check_runbook_sync.py -q` -> `3 passed`;
  - `uv run python scripts/check_runbook_sync.py` -> `script_refs=37`, all refs exist.

49. `P2` Acceptance Toolchain Self-Check Script
- Status: `done`
- Scope:
  - добавить единый self-check для acceptance toolchain scripts/tests;
  - ускорить локальную диагностику целостности acceptance automation перед rollout.
- Progress:
  - добавлен script:
    - `scripts/acceptance_toolchain_self_check.sh`;
  - self-check покрывает:
    - shell syntax acceptance scripts;
    - `check_runbook_sync.py`;
    - extractor unit tests;
    - acceptance ops summary snapshot.
  - runbook дополнен one-command integrity check.
- Validation (April 9, 2026):
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=4 failed=0`;
  - `uv run python scripts/check_runbook_sync.py` -> `script_refs=38`.

50. `P2` Acceptance Reports Index Automation
- Status: `done`
- Scope:
  - добавить markdown index по acceptance-report артефактам;
  - улучшить operator navigation по historical acceptance snapshots.
- Progress:
  - `scripts/acceptance_report_hygiene.py` расширен index generation:
    - `docs/ops/acceptance-reports/INDEX.md`;
  - output hygiene теперь включает `index=<path>`;
  - runbook дополнен ссылкой на acceptance reports index.
- Validation (April 9, 2026):
  - `uv run python scripts/acceptance_report_hygiene.py --keep 50` -> `ok` + `index=docs/ops/acceptance-reports/INDEX.md`;
  - `test -f docs/ops/acceptance-reports/INDEX.md` -> `exists`.

51. `P2` Acceptance Hygiene/Index Test Coverage
- Status: `done`
- Scope:
  - добавить автотесты для `acceptance_report_hygiene.py` (index build + prune preview guards);
  - закрепить стабильность lifecycle logic под CI/self-check.
- Progress:
  - добавлен test module:
    - `scripts/tests/test_acceptance_report_hygiene.py`;
  - покрыты кейсы:
    - index generation + dry-run guardrail;
    - apply prune delete behavior.
  - `acceptance_toolchain_self_check.sh` обновлён:
    - запускает оба test module (`check_runbook_sync` + `acceptance_report_hygiene`).
- Validation (April 9, 2026):
  - `uv run pytest scripts/tests/test_check_runbook_sync.py scripts/tests/test_acceptance_report_hygiene.py -q` -> `5 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=4 failed=0`.

52. `P2` Optional Self-Check Hook In Acceptance Gate
- Status: `done`
- Scope:
  - добавить env-toggle для запуска `acceptance_toolchain_self_check.sh` из acceptance gate;
  - дать оператору строгий режим предгейта без включения по умолчанию.
- Progress:
  - `scripts/autonomous_acceptance_gate.sh` расширен toggle:
    - `HIVE_ACCEPTANCE_RUN_SELF_CHECK` (`false` by default);
  - в `true` режиме gate выполняет:
    - `acceptance_toolchain_self_check.sh` как pre-check step;
  - runbook дополнен новым env knob.
- Validation (April 9, 2026):
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true HIVE_ACCEPTANCE_ENFORCE_HISTORY=true HIVE_ACCEPTANCE_SUMMARY_JSON=true HIVE_ACCEPTANCE_RUN_SELF_CHECK=true ./scripts/autonomous_acceptance_gate.sh`
    -> `ok=14 failed=0`.

53. `P2` Acceptance Launchd Status In Self-Check
- Status: `done`
- Scope:
  - добавить проверку статуса hourly/weekly acceptance launchd в self-check (informational);
  - упростить операторскую диагностику без отдельного запуска snapshot.
- Progress:
  - `scripts/acceptance_toolchain_self_check.sh` расширен:
    - добавлен step `acceptance scheduler snapshot` с `HIVE_ACCEPTANCE_SNAPSHOT_TAIL_LINES=0`;
  - self-check теперь включает launchd-state snapshot (hourly + weekly) как informational check.
- Validation (April 9, 2026):
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=5 failed=0`;
  - snapshot в self-check корректно отражает `not-installed` без failure.

54. `P2` Acceptance Automation Map Doc
- Status: `done`
- Scope:
  - добавить единый документ-карту acceptance automation (scripts + purpose + cadence);
  - упростить onboarding оператора по acceptance контурy.
- Progress:
  - добавлен документ:
    - `docs/ops/acceptance-automation-map.md`;
  - runbook `docs/LOCAL_PROD_RUNBOOK.md` обновлён ссылкой на карту.
- Validation (April 9, 2026):
  - `uv run python scripts/check_runbook_sync.py` -> `ok`, `script_refs=38`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=5 failed=0`.

55. `P2` Factory Docs Cross-Link Hardening
- Status: `done`
- Scope:
  - закрепить discoverability acceptance automation docs из factory docs index;
  - убрать разрыв между `autonomous-factory` и `ops` документацией.
- Progress:
  - `docs/autonomous-factory/README.md` дополнен ссылкой:
    - `../ops/acceptance-automation-map.md`.
  - добавлены cross-links в ops/rollout документы:
    - `docs/autonomous-factory/04-operations-runbook.md`
    - `docs/autonomous-factory/05-rollout-plan.md`.
- Validation (April 9, 2026):
  - `rg -n "acceptance-automation-map" docs/autonomous-factory/README.md docs/autonomous-factory/04-operations-runbook.md docs/autonomous-factory/05-rollout-plan.md docs/LOCAL_PROD_RUNBOOK.md`
    -> ссылки присутствуют во всех целевых точках.

56. `P2` Acceptance Docs Navigation Check Script
- Status: `done`
- Scope:
  - добавить lightweight script, проверяющий ключевые cross-links acceptance docs;
  - включить его в acceptance toolchain self-check.
- Progress:
  - добавлен script:
    - `scripts/check_acceptance_docs_navigation.py`;
  - self-check расширен шагом:
    - `acceptance docs navigation check`;
  - runbook дополнен командой ручной проверки:
    - `uv run python scripts/check_acceptance_docs_navigation.py`.
- Validation (April 9, 2026):
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=6 failed=0`;
  - `uv run python scripts/check_runbook_sync.py` -> `script_refs=39`.

57. `P2` Optional Docs-Nav Check Hook In Acceptance Gate
- Status: `done`
- Scope:
  - добавить env-toggle для запуска `check_acceptance_docs_navigation.py` прямо из acceptance gate;
  - расширить строгий режим gate без включения по умолчанию.
- Progress:
  - `scripts/autonomous_acceptance_gate.sh` расширен toggle:
    - `HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK` (`false` by default);
  - в `true` режиме gate запускает:
    - `uv run python scripts/check_acceptance_docs_navigation.py`;
  - runbook дополнен env knob.
- Validation (April 9, 2026):
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true HIVE_ACCEPTANCE_ENFORCE_HISTORY=true HIVE_ACCEPTANCE_SUMMARY_JSON=true HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK=true ./scripts/autonomous_acceptance_gate.sh`
    -> `ok=14 failed=0`.

58. `P2` Acceptance Gate Env Presets Doc Block
- Status: `done`
- Scope:
  - добавить в runbook готовые env-профили для запуска acceptance gate (fast/strict/full);
  - ускорить операторский запуск без ручной сборки длинных команд.
- Progress:
  - в `docs/LOCAL_PROD_RUNBOOK.md` добавлен блок:
    - `Acceptance gate preset commands`;
  - добавлены 3 preset режима:
    - `fast local smoke`,
    - `strict historical gate`,
    - `full strict + self-check + docs-nav`.
- Validation (April 9, 2026):
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true HIVE_ACCEPTANCE_SKIP_TELEGRAM=true ./scripts/autonomous_acceptance_gate.sh` -> `ok=11 failed=0`;
  - runbook содержит preset block (`rg -n "Acceptance gate preset commands"`).

59. `P2` Acceptance Gate Preset Helper Script
- Status: `done`
- Scope:
  - добавить helper script для запуска acceptance gate пресетов `fast|strict|full`;
  - сократить ручной env boilerplate в operator daily workflow.
- Progress:
  - добавлен script:
    - `scripts/acceptance_gate_presets.sh`;
  - поддерживаются preset режимы:
    - `fast`, `strict`, `full`;
  - runbook дополнен helper-командами.
- Validation (April 9, 2026):
  - `./scripts/acceptance_gate_presets.sh fast` -> `ok=11 failed=0`;
  - `./scripts/acceptance_gate_presets.sh strict` -> `ok=13 failed=0`;
  - `uv run python scripts/check_runbook_sync.py` -> `script_refs=40`.

60. `P2` Preset Helper Dry-Run Mode
- Status: `done`
- Scope:
  - добавить dry-run/env-preview режим в `acceptance_gate_presets.sh` без выполнения gate;
  - облегчить безопасную проверку preset-конфигурации.
- Progress:
  - `scripts/acceptance_gate_presets.sh` расширен флагом:
    - `--print-env-only`;
  - print-only режим печатает preset env и завершает работу без запуска gate;
  - runbook дополнен preview-командой.
- Validation (April 9, 2026):
  - `./scripts/acceptance_gate_presets.sh fast --print-env-only` -> `ok`;
  - `./scripts/acceptance_gate_presets.sh strict --print-env-only` -> `ok`;
  - `./scripts/acceptance_gate_presets.sh full --print-env-only` -> `ok`.

61. `P2` Preset Helper Test Coverage
- Status: `done`
- Scope:
  - добавить автотесты на `acceptance_gate_presets.sh` (fast/strict/full print-only);
  - включить тест в acceptance toolchain self-check.
- Progress:
  - добавлен test module:
    - `scripts/tests/test_acceptance_gate_presets.py`;
  - покрыты режимы:
    - `fast --print-env-only`,
    - `strict --print-env-only`,
    - `full --print-env-only`;
  - `acceptance_toolchain_self_check.sh` обновлён:
    - включает тест preset-helper вместе с остальными acceptance unit tests.
- Validation (April 9, 2026):
  - `uv run pytest scripts/tests/test_acceptance_gate_presets.py -q` -> `3 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=6 failed=0` (`8 passed` unit tests aggregate).

62. `P2` Acceptance Map Presets Section
- Status: `done`
- Scope:
  - добавить в `docs/ops/acceptance-automation-map.md` отдельный блок по preset-helper;
  - сделать entrypoint по режимам (`fast|strict|full`) видимым в карте автоматизации.
- Progress:
  - в `docs/ops/acceptance-automation-map.md` добавлен блок:
    - `scripts/acceptance_gate_presets.sh` с описанием режимов `fast|strict|full`;
  - добавлена заметка про `--print-env-only`.
- Validation (April 9, 2026):
  - `rg -n "acceptance_gate_presets|print-env-only" docs/ops/acceptance-automation-map.md` -> matches found;
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`.

63. `P2` Acceptance Map Quick-Start Block
- Status: `done`
- Scope:
  - добавить в acceptance map короткий quick-start из 3 команд (`fast|strict|full`);
  - ускорить onboarding операторов без чтения полного runbook.
- Progress:
  - добавлен `Quick Start` section в `docs/ops/acceptance-automation-map.md`.
- Validation (April 9, 2026):
  - `rg -n "## Quick Start|acceptance_gate_presets\\.sh (fast|strict|full)" docs/ops/acceptance-automation-map.md` -> all 3 commands present;
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=6 failed=0` (`10 passed` unit tests).

64. `P2` Preset Helper Project Scope Support
- Status: `done`
- Scope:
  - добавить в `acceptance_gate_presets.sh` поддержку project scope (`HIVE_ACCEPTANCE_PROJECT_ID`);
  - дать оператору короткий запуск пресета на конкретный проект без ручного env экспорта.
- Progress:
  - `scripts/acceptance_gate_presets.sh` расширен флагом:
    - `--project <id>`;
  - при указании `--project` скрипт выставляет:
    - `HIVE_ACCEPTANCE_PROJECT_ID=<id>`;
  - runbook дополнен примером:
    - `./scripts/acceptance_gate_presets.sh strict --project default`.
- Validation (April 9, 2026):
  - `./scripts/acceptance_gate_presets.sh strict --project default --print-env-only` -> печатает `HIVE_ACCEPTANCE_PROJECT_ID=default`;
  - `uv run pytest scripts/tests/test_acceptance_gate_presets.py -q` -> `4 passed`.

65. `P2` Preset Helper Error-Path Test Coverage
- Status: `done`
- Scope:
  - добавить тесты на error-path CLI preset-helper (`unknown mode`, `--project` без value);
  - закрепить корректный non-zero exit и usage/error output.
- Progress:
  - `scripts/tests/test_acceptance_gate_presets.py` расширен negative cases:
    - `unknown mode` -> non-zero + `usage` in stderr;
    - `--project` без value -> non-zero + explicit error.
- Validation (April 9, 2026):
  - `uv run pytest scripts/tests/test_acceptance_gate_presets.py -q` -> `6 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=6 failed=0` (`13 passed` unit tests aggregate).

66. `P2` Preset Helper Error Behavior Docs
- Status: `done`
- Scope:
  - добавить в runbook короткий блок ожидаемого поведения preset-helper при ошибках CLI;
  - сократить операторские вопросы при неверном вызове скрипта.
- Progress:
  - в runbook добавлен блок `Preset helper error behavior`:
    - unknown mode -> non-zero + usage;
    - missing `--project` value -> non-zero + explicit error.
  - acceptance automation map дополнен error behavior notes для preset-helper.
- Validation (April 9, 2026):
  - `rg -n "Preset helper error behavior|--project requires value" docs/LOCAL_PROD_RUNBOOK.md scripts/acceptance_gate_presets.sh` -> matches found;
  - `uv run pytest scripts/tests/test_acceptance_gate_presets.py -q` -> `6 passed`.

67. `P2` Preset Matrix Smoke Script
- Status: `done`
- Scope:
  - добавить one-command smoke matrix для preset-helper (`fast|strict|full` + project override);
  - использовать smoke как быстрый operator sanity-check пресетов.
- Progress:
  - добавлен script:
    - `scripts/acceptance_gate_presets_smoke.sh`;
  - runbook дополнен командой:
    - `./scripts/acceptance_gate_presets_smoke.sh`.
- Validation (April 9, 2026):
  - `./scripts/acceptance_gate_presets_smoke.sh` -> `ok=4 failed=0`;
  - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true ./scripts/acceptance_toolchain_self_check.sh`
    -> `ok=7 failed=0`.

68. `P2` Optional Preset Smoke Hook In Acceptance Gate
- Status: `done`
- Scope:
  - добавить env-toggle для запуска `acceptance_gate_presets_smoke.sh` внутри acceptance gate;
  - дать оператору опциональный deep-check без включения по умолчанию.
- Progress:
  - `scripts/autonomous_acceptance_gate.sh` расширен toggle:
    - `HIVE_ACCEPTANCE_RUN_PRESET_SMOKE` (`false` by default);
  - в `true` режиме gate запускает:
    - `./scripts/acceptance_gate_presets_smoke.sh`.
  - runbook дополнен новым env knob.
- Validation (April 9, 2026):
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true HIVE_ACCEPTANCE_SKIP_TELEGRAM=true HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=true ./scripts/autonomous_acceptance_gate.sh`
    -> `ok=12 failed=0`.

69. `P2` Acceptance Gate Toggles Quick Reference
- Status: `done`
- Scope:
  - добавить в runbook compact таблицу/список gate toggles и их эффекта;
  - ускорить выбор режима оператором без чтения длинных секций.
- Progress:
  - в `docs/LOCAL_PROD_RUNBOOK.md` добавлен блок:
    - `Acceptance gate toggles quick reference`;
  - quick-reference покрывает ключевые toggles:
    - `SKIP_CHECKLIST`, `SKIP_TELEGRAM`, `ENFORCE_HISTORY`, `SUMMARY_JSON`,
      `RUN_SELF_CHECK`, `RUN_DOCS_NAV_CHECK`, `RUN_PRESET_SMOKE`.
- Validation (April 9, 2026):
  - `rg -n "Acceptance gate toggles quick reference|HIVE_ACCEPTANCE_RUN_PRESET_SMOKE" docs/LOCAL_PROD_RUNBOOK.md` -> matches found;
  - `uv run python scripts/check_runbook_sync.py` -> `ok`.

70. `P2` Acceptance Toggles Sync Check
- Status: `done`
- Scope:
  - добавить script, проверяющий согласованность ключевых `HIVE_ACCEPTANCE_*` toggles
    между `autonomous_acceptance_gate.sh` и runbook;
  - снизить риск drift при добавлении новых toggles.
- Progress:
  - добавлен script:
    - `scripts/check_acceptance_gate_toggles_sync.py`;
  - `acceptance_toolchain_self_check.sh` расширен шагом:
    - `acceptance gate toggles sync check`;
  - runbook дополнен командой ручной проверки:
    - `uv run python scripts/check_acceptance_gate_toggles_sync.py`.
- Validation (April 9, 2026):
  - `uv run python scripts/check_acceptance_gate_toggles_sync.py` -> all toggles `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=7 failed=0`;
  - `uv run python scripts/check_runbook_sync.py` -> `script_refs=42`.

71. `P2` Self-Check Optional Preset-Smoke Docs
- Status: `done`
- Scope:
  - отразить в acceptance automation map, что preset smoke в self-check запускается через
    `HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true`;
  - упростить операторский выбор между fast и deep self-check.
- Progress:
  - в `docs/ops/acceptance-automation-map.md` добавлен `Optional deep mode` для self-check;
  - в runbook уже присутствует команда:
    - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true ./scripts/acceptance_toolchain_self_check.sh`.
- Validation (April 9, 2026):
  - `rg -n "HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE|Optional deep mode" docs/ops/acceptance-automation-map.md docs/LOCAL_PROD_RUNBOOK.md` -> matches found;
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`.

72. `P2` Toggles Sync Checker Test Coverage
- Status: `done`
- Scope:
  - добавить unit-тесты для `check_acceptance_gate_toggles_sync.py` (pass/fail cases);
  - закрепить стабильность toggle-sync guard в acceptance toolchain.
- Progress:
  - добавлен test module:
    - `scripts/tests/test_check_acceptance_gate_toggles_sync.py`;
  - покрыты кейсы:
    - pass (all toggles present),
    - fail (missing toggles in runbook side).
  - `acceptance_toolchain_self_check.sh` обновлён:
    - включает новый test module в unit-tests step.
- Validation (April 9, 2026):
  - `uv run pytest scripts/tests/test_check_acceptance_gate_toggles_sync.py -q` -> `2 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=7 failed=0` (`15 passed` unit tests aggregate).

73. `P2` Acceptance Map Toggle-Sync Guard Docs
- Status: `done`
- Scope:
  - отразить в `docs/ops/acceptance-automation-map.md` наличие toggle-sync guard (`check_acceptance_gate_toggles_sync.py`);
  - подчеркнуть его назначение как anti-drift контроля.
- Progress:
  - в `docs/ops/acceptance-automation-map.md` добавлен guardrail блок:
    - `scripts/check_acceptance_gate_toggles_sync.py`;
  - `check_acceptance_docs_navigation.py` расширен:
    - теперь валидирует наличие toggle-sync guard и deep self-check marker в acceptance map.
  - обновлён test module `test_check_acceptance_docs_navigation.py`.
- Validation (April 9, 2026):
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`;
  - `uv run pytest scripts/tests/test_check_acceptance_docs_navigation.py -q` -> `2 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=7 failed=0`.

74. `P2` Docs-Nav Default-Checks Regression Test
- Status: `done`
- Scope:
  - добавить тест, который валидирует содержимое default `CHECKS` в
    `check_acceptance_docs_navigation.py` (чтобы обязательные маркеры не выпадали);
  - снизить риск тихого регресса при редактировании checker constants.
- Progress:
  - в `scripts/tests/test_check_acceptance_docs_navigation.py` добавлен regression test:
    - `test_default_checks_include_required_acceptance_map_markers`;
  - проверка усилена:
    - default `CHECKS` теперь явно валидирует обязательные маркеры quick-start и guardrails.
- Validation (April 9, 2026):
  - `uv run pytest scripts/tests/test_check_acceptance_docs_navigation.py -q` -> `3 passed`;
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`.

75. `P2` Self-Check Optional Runtime Parity Hook
- Status: `done`
- Scope:
  - добавить optional toggle для включения live runtime parity (`check_runtime_parity.sh`) в
    `acceptance_toolchain_self_check.sh`;
  - зафиксировать toggle в операторской документации и docs-navigation guard.
- Progress:
  - `scripts/acceptance_toolchain_self_check.sh` расширен env toggle:
    - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY` (`false` by default);
  - при `true` self-check запускает:
    - `./scripts/check_runtime_parity.sh`;
  - `docs/ops/acceptance-automation-map.md` и `docs/LOCAL_PROD_RUNBOOK.md` обновлены
    командой deep self-check с runtime parity;
  - `scripts/check_acceptance_docs_navigation.py` и
    `scripts/tests/test_check_acceptance_docs_navigation.py` обновлены новым required marker.
- Validation (April 9, 2026):
  - `./scripts/check_runtime_parity.sh` -> `runtime parity check passed`;
  - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh`
    -> `ok=8 failed=0`;
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`;
  - `uv run pytest scripts/tests/test_check_acceptance_docs_navigation.py -q` -> `3 passed`.

76. `P2` Self-Check Runtime-Parity Toggle Regression Coverage
- Status: `done`
- Scope:
  - добавить unit/regression test, который фиксирует наличие runtime-parity toggle/branch
    в `acceptance_toolchain_self_check.sh`;
  - включить test в стандартный self-check test bundle.
- Progress:
  - добавлен test module:
    - `scripts/tests/test_acceptance_toolchain_self_check_script.py`;
  - test валидирует:
    - env toggle declaration,
    - runtime echo marker,
    - `if`-branch,
    - `run_step` runtime parity check,
    - skip-marker.
  - `acceptance_toolchain_self_check.sh` обновлён:
    - новый test module включён в `acceptance unit tests` step.
- Validation (April 9, 2026):
  - `uv run pytest scripts/tests/test_acceptance_toolchain_self_check_script.py -q` -> `1 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `17 passed`, `ok=7 failed=0`;
  - `uv run python scripts/backlog_status.py` -> `in_progress=[76]` (pre-close snapshot).

77. `P2` Composite Deep Self-Check Profile Docs + Nav Guard
- Status: `done`
- Scope:
  - зафиксировать в operator docs единый composite deep-profile запуска self-check:
    preset smoke + runtime parity;
  - включить этот marker в docs-navigation guard, чтобы исключить drift.
- Progress:
  - `docs/ops/acceptance-automation-map.md` дополнен командой:
    - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh`;
  - `docs/LOCAL_PROD_RUNBOOK.md` дополнен блоком full deep self-check profile;
  - `scripts/check_acceptance_docs_navigation.py` обновлён новым required marker;
  - `scripts/tests/test_check_acceptance_docs_navigation.py` синхронизирован под новый marker.
- Validation (April 9, 2026):
  - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh`
    -> `ok=9 failed=0`;
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`;
  - `uv run pytest scripts/tests/test_check_acceptance_docs_navigation.py -q` -> `3 passed`.

78. `P2` Deep Self-Check Wrapper + Regression Coverage
- Status: `done`
- Scope:
  - добавить one-command wrapper для полного deep self-check профиля;
  - зафиксировать wrapper в docs и docs-navigation guard;
  - покрыть wrapper regression test и включить его в self-check unit bundle.
- Progress:
  - добавлен executable script:
    - `scripts/acceptance_toolchain_self_check_deep.sh`;
  - wrapper экспортирует:
    - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true`,
    - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true`,
    - и делегирует в `acceptance_toolchain_self_check.sh`;
  - обновлены docs:
    - `docs/ops/acceptance-automation-map.md`,
    - `docs/LOCAL_PROD_RUNBOOK.md`;
  - docs-nav checker/test обновлены новым required marker:
    - `./scripts/acceptance_toolchain_self_check_deep.sh`;
  - добавлен test module:
    - `scripts/tests/test_acceptance_toolchain_self_check_deep_script.py`;
  - `acceptance_toolchain_self_check.sh` unit-tests step расширен новым test module.
  - `acceptance_toolchain_self_check.sh` shell syntax step расширен:
    - включает `scripts/acceptance_toolchain_self_check_deep.sh`;
  - `scripts/tests/test_acceptance_toolchain_self_check_script.py` усилен
    проверкой присутствия deep wrapper в shell syntax guard.
- Validation (April 10, 2026):
  - `./scripts/acceptance_toolchain_self_check_deep.sh` -> `ok=9 failed=0`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `18 passed`, `ok=7 failed=0`;
  - `uv run pytest scripts/tests/test_acceptance_toolchain_self_check_deep_script.py scripts/tests/test_check_acceptance_docs_navigation.py -q`
    -> `4 passed`;
  - `uv run python scripts/check_runbook_sync.py` -> `script_refs=43`.

79. `P2` Archive/Index Hygiene Guard In Acceptance Self-Check
- Status: `done`
- Scope:
  - добавить explicit checker для `docs/autonomous-factory/archive/INDEX.md`;
  - включить checker в `acceptance_toolchain_self_check.sh`;
  - устранить дрейф `unknown` timestamps в archive index generation.
- Progress:
  - исправлен timestamp parse в `scripts/backlog_archive_hygiene.py`
    (`_parse_stamp` теперь корректно обрабатывает `backlog-done-snapshot-YYYYmmdd-HHMMSS`);
  - добавлен checker:
    - `scripts/check_backlog_archive_index.py`;
  - checker валидирует:
    - отсутствие `unknown` timestamp marker,
    - что все snapshot files присутствуют в index,
    - отсутствие stale refs в index;
  - добавлены тесты:
    - `scripts/tests/test_check_backlog_archive_index.py`;
  - `acceptance_toolchain_self_check.sh` расширен шагом:
    - `backlog archive index check`;
  - unit bundle self-check расширен новым test module;
  - docs обновлены:
    - `docs/ops/acceptance-automation-map.md`,
    - `docs/LOCAL_PROD_RUNBOOK.md`.
- Validation (April 10, 2026):
  - `uv run python scripts/backlog_archive_hygiene.py` -> regenerated archive index with concrete timestamp;
  - `uv run python scripts/check_backlog_archive_index.py` -> `ok`;
  - `uv run pytest scripts/tests/test_check_backlog_archive_index.py -q` -> `2 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> includes `backlog archive index check`, `20 passed`, `ok=8 failed=0`.

80. `P2` Regression Guard For Archive Index Self-Check Step
- Status: `done`
- Scope:
  - зафиксировать через test, что `acceptance_toolchain_self_check.sh`
    содержит шаг `backlog archive index check` и test module checker-а;
  - предотвратить тихий выпадение archive/index guard из self-check.
- Progress:
  - `scripts/tests/test_acceptance_toolchain_self_check_script.py` усилен:
    - проверяет наличие строки
      `run_step "backlog archive index check" uv run python scripts/check_backlog_archive_index.py`;
    - проверяет включение `scripts/tests/test_check_backlog_archive_index.py`
      в self-check unit bundle;
  - тесты и self-check прогнаны успешно.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_acceptance_toolchain_self_check_script.py scripts/tests/test_check_backlog_archive_index.py -q`
    -> `3 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `20 passed`, `ok=8 failed=0`.

81. `P2` Docs-Nav Guard For Archive Index Checker Marker
- Status: `done`
- Scope:
  - включить `scripts/check_backlog_archive_index.py` в required markers
    `check_acceptance_docs_navigation.py`;
  - обновить tests, чтобы выпадение маркера ловилось regression suite.
- Progress:
  - `scripts/check_acceptance_docs_navigation.py` расширен marker:
    - `scripts/check_backlog_archive_index.py`;
  - обновлён `scripts/tests/test_check_acceptance_docs_navigation.py`
    (fixtures + default checks assertions);
  - прогнаны docs-nav checker, соответствующие tests и полный self-check.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_check_acceptance_docs_navigation.py -q` -> `3 passed`;
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `20 passed`, `ok=8 failed=0`.

82. `P2` Acceptance Preset `full-deep` Profile
- Status: `done`
- Scope:
  - добавить режим `full-deep` в `acceptance_gate_presets.sh` для one-command глубокого прогона:
    `full` + preset smoke + runtime parity inside self-check;
  - синхронизировать preset smoke matrix, docs, docs-nav guard и tests.
- Progress:
  - `scripts/acceptance_gate_presets.sh` расширен mode:
    - `full-deep`;
  - `full-deep` выставляет:
    - `HIVE_ACCEPTANCE_RUN_SELF_CHECK=true`,
    - `HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK=true`,
    - `HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=true`,
    - `HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true`,
    - плюс strict-базу (`skip_checklist`, `enforce_history`, `summary_json`);
  - usage/help обновлён: `[fast|strict|full|full-deep]`;
  - `scripts/acceptance_gate_presets_smoke.sh` дополнен шагом
    `preset full-deep print-only`;
  - `scripts/tests/test_acceptance_gate_presets.py` расширен test case `full-deep`;
  - docs обновлены:
    - `docs/ops/acceptance-automation-map.md`,
    - `docs/LOCAL_PROD_RUNBOOK.md`;
  - docs-nav checker/test обновлены marker-ом:
    - `./scripts/acceptance_gate_presets.sh full-deep`.
- Validation (April 10, 2026):
  - `./scripts/acceptance_gate_presets.sh full-deep --print-env-only` -> expected env profile printed;
  - `HIVE_ACCEPTANCE_SKIP_TELEGRAM=true ./scripts/acceptance_gate_presets.sh full-deep` -> acceptance gate `ok=15 failed=0`;
  - `uv run pytest scripts/tests/test_acceptance_gate_presets.py scripts/tests/test_check_acceptance_docs_navigation.py scripts/tests/test_check_backlog_archive_index.py -q`
    -> `12 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `22 passed`, `ok=8 failed=0`.

83. `P2` Deterministic Preset-Smoke Env Isolation
- Status: `done`
- Scope:
  - убрать наследование env из внешнего запуска в `acceptance_gate_presets_smoke.sh`,
    чтобы `fast|strict|full|full-deep` print-only output был детерминированным;
  - закрепить поведение regression test-ом.
- Progress:
  - в `scripts/acceptance_gate_presets_smoke.sh` добавлен wrapper:
    - `run_clean_preset` (через `env -u` для ключевых `HIVE_ACCEPTANCE_*` переменных);
  - smoke matrix переведена на `run_clean_preset` для всех preset checks;
  - добавлен test module:
    - `scripts/tests/test_acceptance_gate_presets_smoke_script.py`;
  - `acceptance_toolchain_self_check.sh` unit-tests bundle расширен новым test module;
  - выявлен и исправлен дефект preset launcher при пустых extra args:
    - `scripts/acceptance_gate_presets.sh` теперь безопасно обрабатывает empty `filtered_args` под `set -u`.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_acceptance_gate_presets.py scripts/tests/test_acceptance_gate_presets_smoke_script.py scripts/tests/test_acceptance_gate_presets_smoke_behavior.py -q`
    -> `10 passed`;
  - `./scripts/acceptance_gate_presets_smoke.sh` -> `ok=5 failed=0` и детерминированные profiles;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `24 passed`, `ok=8 failed=0`.

84. `P2` Preset Mode Contract Regression Tests
- Status: `done`
- Scope:
  - зафиксировать контракт ключевых flags для режимов
    `fast|strict|full|full-deep` в `acceptance_gate_presets.sh`;
  - снизить риск дрейфа preset semantics при будущих правках.
- Progress:
  - в `scripts/tests/test_acceptance_gate_presets.py` добавлен helper `_extract_value`;
  - добавлен test:
    - `test_mode_contract_flags_are_stable`;
  - тест валидирует per-mode contract:
    - `fast`: guard/history/self-check/smoke flags unset,
    - `strict`: history/json enabled, self-check/smoke unset,
    - `full`: history + self-check enabled, smoke unset,
    - `full-deep`: history + self-check + smoke + runtime parity enabled.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_acceptance_gate_presets.py scripts/tests/test_acceptance_gate_presets_smoke_behavior.py -q`
    -> `10 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `25 passed`, `ok=8 failed=0`.

85. `P2` Preset Contract Sync Checker (Script/Smoke/Docs)
- Status: `done`
- Scope:
  - добавить explicit checker, validating preset mode markers across:
    `acceptance_gate_presets.sh`, `acceptance_gate_presets_smoke.sh`, docs map;
  - включить checker в self-check и покрыть тестами.
- Progress:
  - добавлен checker:
    - `scripts/check_acceptance_preset_contract_sync.py`;
  - checker валидирует наличие contract markers:
    - mode branches + usage в preset launcher,
    - smoke steps (`fast|strict|full|full-deep`),
    - quick-start preset commands в `docs/ops/acceptance-automation-map.md`;
  - добавлены tests:
    - `scripts/tests/test_check_acceptance_preset_contract_sync.py`;
  - `scripts/acceptance_toolchain_self_check.sh` расширен шагом:
    - `acceptance preset contract sync check`;
  - self-check unit bundle расширен новым test module;
  - docs updated:
    - `docs/ops/acceptance-automation-map.md`,
    - `docs/LOCAL_PROD_RUNBOOK.md`.
- Validation (April 10, 2026):
  - `uv run python scripts/check_acceptance_preset_contract_sync.py` -> `ok`;
  - `uv run pytest scripts/tests/test_check_acceptance_preset_contract_sync.py scripts/tests/test_acceptance_gate_presets.py -q`
    -> `11 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> includes `acceptance preset contract sync check`, `27 passed`, `ok=9 failed=0`.

86. `P2` Docs-Nav Guard For Preset-Contract Checker Marker
- Status: `done`
- Scope:
  - добавить marker `scripts/check_acceptance_preset_contract_sync.py`
    в required checks docs-navigation guard;
  - расширить regression tests, чтобы выпадение checker-marker ловилось автоматически.
- Progress:
  - `scripts/check_acceptance_docs_navigation.py` расширен новым required marker:
    - `scripts/check_acceptance_preset_contract_sync.py`;
  - обновлён `scripts/tests/test_check_acceptance_docs_navigation.py`
    (fixtures + default checks assertions);
  - корректировка тест-фикстуры завершена, test suite зелёный;
  - прогнан полный self-check после фикса.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_check_acceptance_docs_navigation.py scripts/tests/test_check_acceptance_preset_contract_sync.py -q`
    -> `5 passed`;
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `27 passed`, `ok=9 failed=0`.

87. `P2` Runtime Determinism Checker For Preset-Smoke Matrix
- Status: `done`
- Scope:
  - добавить shell-level checker, который запускает preset smoke в загрязнённом `HIVE_ACCEPTANCE_*` env
    и проверяет детерминированность профилей;
  - включить checker в self-check и покрыть regression test-ом.
- Progress:
  - добавлен executable checker:
    - `scripts/check_acceptance_preset_smoke_determinism.sh`;
  - checker:
    - запускает `acceptance_gate_presets_smoke.sh` под загрязнённым env,
    - проверяет, что `fast`/`strict` не наследуют лишние флаги,
    - проверяет, что `full-deep` сохраняет `RUN_PRESET_SMOKE=true` и
      `SELF_CHECK_RUN_RUNTIME_PARITY=true`;
  - добавлен test module:
    - `scripts/tests/test_check_acceptance_preset_smoke_determinism_script.py`;
  - `acceptance_toolchain_self_check.sh` расширен шагом:
    - `acceptance preset smoke determinism check`;
  - unit bundle self-check расширен новым test module;
  - docs updated:
    - `docs/ops/acceptance-automation-map.md`,
    - `docs/LOCAL_PROD_RUNBOOK.md`.
- Validation (April 10, 2026):
  - `./scripts/check_acceptance_preset_smoke_determinism.sh` -> `ok`;
  - `uv run pytest scripts/tests/test_check_acceptance_preset_smoke_determinism_script.py scripts/tests/test_check_acceptance_preset_contract_sync.py -q`
    -> `3 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> includes determinism step, `28 passed`, `ok=10 failed=0`.

88. `P2` Docs-Nav Guard For Preset-Smoke Determinism Checker
- Status: `done`
- Scope:
  - добавить marker `scripts/check_acceptance_preset_smoke_determinism.sh`
    в docs-navigation required checks;
  - обновить regression tests, чтобы выпадение marker-а не проходило незамеченным.
- Progress:
  - `scripts/check_acceptance_docs_navigation.py` расширен новым required marker:
    - `scripts/check_acceptance_preset_smoke_determinism.sh`;
  - `scripts/tests/test_check_acceptance_docs_navigation.py` обновлён
    (fixtures + default checks assertions);
  - прогнаны docs-nav checker, determinism checker, targeted tests и полный self-check.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_check_acceptance_docs_navigation.py scripts/tests/test_check_acceptance_preset_smoke_determinism_script.py -q`
    -> `4 passed`;
  - `uv run python scripts/check_acceptance_docs_navigation.py && ./scripts/check_acceptance_preset_smoke_determinism.sh` -> `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `30 passed`, `ok=11 failed=0`.

89. `P2` Acceptance Guardrails Sync Checker
- Status: `done`
- Scope:
  - синхронизировать обязательные acceptance guardrails между
    `acceptance_toolchain_self_check.sh` и `docs/ops/acceptance-automation-map.md`;
  - добавить явный checker + tests и включить его в self-check flow.
- Progress:
  - добавлен checker:
    - `scripts/check_acceptance_guardrails_sync.py`;
  - checker валидирует presence markers для:
    - `check_acceptance_gate_toggles_sync.py`,
    - `check_acceptance_docs_navigation.py`,
    - `check_acceptance_preset_contract_sync.py`,
    - `check_acceptance_preset_smoke_determinism.sh`,
    - `check_backlog_archive_index.py`;
  - добавлен test module:
    - `scripts/tests/test_check_acceptance_guardrails_sync.py`;
  - `acceptance_toolchain_self_check.sh` расширен шагом:
    - `acceptance guardrails sync check`;
  - self-check unit bundle расширен test module для guardrails sync checker;
  - docs updated:
    - `docs/ops/acceptance-automation-map.md`,
    - `docs/LOCAL_PROD_RUNBOOK.md`;
  - docs-nav guard дополнен marker:
    - `scripts/check_acceptance_guardrails_sync.py`.
- Validation (April 10, 2026):
  - `uv run python scripts/check_acceptance_guardrails_sync.py` -> `ok`;
  - `uv run pytest scripts/tests/test_check_acceptance_guardrails_sync.py scripts/tests/test_check_acceptance_docs_navigation.py -q`
    -> `5 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> includes guardrails sync step, `30 passed`, `ok=11 failed=0`.

90. `P2` Self-Check Pytest Bundle Sync Checker
- Status: `done`
- Scope:
  - добавить checker, валидирующий что ключевые acceptance test modules
    присутствуют в `acceptance_toolchain_self_check.sh` pytest bundle;
  - включить checker в self-check flow и покрыть regression tests;
  - отразить checker в operator docs.
- Progress:
  - добавлен checker:
    - `scripts/check_acceptance_self_check_test_bundle_sync.py`;
  - checker валидирует presence required test modules в self-check script;
  - добавлен test module:
    - `scripts/tests/test_check_acceptance_self_check_test_bundle_sync.py`;
  - `acceptance_toolchain_self_check.sh` расширен шагом:
    - `acceptance self-check test-bundle sync check`;
  - self-check unit bundle расширен новым test module;
  - docs updated:
    - `docs/ops/acceptance-automation-map.md`,
    - `docs/LOCAL_PROD_RUNBOOK.md`.
- Validation (April 10, 2026):
  - `uv run python scripts/check_acceptance_self_check_test_bundle_sync.py` -> `ok`;
  - `uv run pytest scripts/tests/test_check_acceptance_self_check_test_bundle_sync.py scripts/tests/test_check_acceptance_guardrails_sync.py -q`
    -> `4 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> includes test-bundle sync step, `32 passed`, `ok=12 failed=0`.

91. `P2` Docs-Nav Guard For Self-Check Test-Bundle Checker
- Status: `done`
- Scope:
  - добавить marker `scripts/check_acceptance_self_check_test_bundle_sync.py`
    в docs-navigation required checks;
  - обновить regression tests и исключить выпадение marker-а из docs map.
- Progress:
  - `scripts/check_acceptance_docs_navigation.py` расширен marker:
    - `scripts/check_acceptance_self_check_test_bundle_sync.py`;
  - обновлён `scripts/tests/test_check_acceptance_docs_navigation.py`
    (fixtures + default checks assertions);
  - прогнаны docs-navigation checker, target tests и полный self-check.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_check_acceptance_docs_navigation.py scripts/tests/test_check_acceptance_self_check_test_bundle_sync.py -q`
    -> `5 passed`;
  - `uv run python scripts/check_acceptance_docs_navigation.py && uv run python scripts/check_acceptance_self_check_test_bundle_sync.py`
    -> `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `32 passed`, `ok=12 failed=0`.

92. `P2` Guardrails-Sync Coverage For Self-Check Bundle Checker
- Status: `done`
- Scope:
  - добавить `scripts/check_acceptance_self_check_test_bundle_sync.py`
    в обязательный список `check_acceptance_guardrails_sync.py`;
  - обновить regression tests для guardrails sync checker;
  - подтвердить green self-check после расширения guardrail set.
- Progress:
  - `scripts/check_acceptance_guardrails_sync.py` расширен marker-ом:
    - `scripts/check_acceptance_self_check_test_bundle_sync.py`;
  - обновлён `scripts/tests/test_check_acceptance_guardrails_sync.py`;
  - прогнаны targeted tests и полный self-check.
- Validation (April 10, 2026):
  - `uv run python scripts/check_acceptance_guardrails_sync.py` -> `ok`;
  - `uv run pytest scripts/tests/test_check_acceptance_guardrails_sync.py scripts/tests/test_check_acceptance_self_check_test_bundle_sync.py -q`
    -> `4 passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `32 passed`, `ok=12 failed=0`.

93. `P2` Guardrail Marker-Set Sync Checker Integration
- Status: `done`
- Scope:
  - добавить checker для set-sync между `GUARDRAIL_SCRIPTS` и docs-nav acceptance-map markers;
  - включить checker в self-check, tests bundle и operator docs;
  - исключить false positives для meta guardrails.
- Progress:
  - добавлен checker:
    - `scripts/check_acceptance_guardrail_marker_set_sync.py`;
  - checker сравнивает marker sets между:
    - `check_acceptance_guardrails_sync.py` (`GUARDRAIL_SCRIPTS`),
    - `check_acceptance_docs_navigation.py` (`CHECKS` для acceptance map);
  - добавлен `EXCLUDED_MARKERS` для meta checkers;
  - добавлен test module:
    - `scripts/tests/test_check_acceptance_guardrail_marker_set_sync.py`;
  - `acceptance_toolchain_self_check.sh` расширен шагом:
    - `acceptance guardrail marker-set sync check`;
  - unit bundle self-check расширен новым test module;
  - docs updated:
    - `docs/ops/acceptance-automation-map.md`,
    - `docs/LOCAL_PROD_RUNBOOK.md`;
  - docs-nav guard расширен marker-ом:
    - `scripts/check_acceptance_guardrail_marker_set_sync.py`;
  - `check_acceptance_self_check_test_bundle_sync.py` required modules обновлён
    новым test module marker.
- Validation (April 10, 2026):
  - `uv run python scripts/check_acceptance_guardrail_marker_set_sync.py` -> `ok`;
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`;
  - `uv run python scripts/check_acceptance_guardrails_sync.py` -> `ok`;
  - `uv run python scripts/check_acceptance_self_check_test_bundle_sync.py` -> `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=14 failed=0`.

94. `P2` Backlog Status Consistency Checker Integration
- Status: `done`
- Scope:
  - добавить checker, который валидирует консистентность parser logic между
    `scripts/backlog_status.py` и `scripts/validate_backlog_markdown.py`;
  - включить checker в self-check flow, docs map и runbook sanity commands;
  - добавить regression tests и зафиксировать marker sync.
- Progress:
  - добавлен checker:
    - `scripts/check_backlog_status_consistency.py`;
  - checker сравнивает parser outputs на уровне:
    - `task_ids`,
    - `in_progress`,
    - `Current Focus refs`,
    - отсутствия `unknown` statuses в status parser;
  - добавлен test module:
    - `scripts/tests/test_check_backlog_status_consistency.py`;
  - `acceptance_toolchain_self_check.sh` расширен шагом:
    - `backlog status consistency check`;
  - `acceptance unit tests` bundle расширен новым test module;
  - guardrails/docs sync расширены marker-ом:
    - `scripts/check_backlog_status_consistency.py`;
  - runbook sanity command-set расширен командой:
    - `uv run python scripts/check_backlog_status_consistency.py`.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_check_backlog_status_consistency.py scripts/tests/test_check_acceptance_guardrail_marker_set_sync.py scripts/tests/test_check_acceptance_docs_navigation.py scripts/tests/test_check_acceptance_guardrails_sync.py scripts/tests/test_acceptance_toolchain_self_check_script.py -q`
    -> `10 passed`;
  - `uv run python scripts/check_backlog_status_consistency.py` -> `ok`;
  - `uv run python scripts/check_acceptance_guardrail_marker_set_sync.py` -> `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `41 passed`, `ok=15 failed=0`.

95. `P2` Backlog Status JSON Contract Hardening
- Status: `done`
- Scope:
  - добавить в `scripts/backlog_status.py` машиночитаемый режим вывода (`--json`)
    для automation hooks;
  - добавить regression tests для text/json/missing-file сценариев;
  - включить новый test module в self-check bundle и синхронные guardrail checkers.
- Progress:
  - `scripts/backlog_status.py` расширен CLI flags:
    - `--path` (custom backlog path);
    - `--json` (machine-readable payload with `tasks_total/status_counts/in_progress/focus_refs/focus_items`);
  - выделен общий parser helper `_parse_backlog(...)` для единообразного text/json output;
  - добавлен test module:
    - `scripts/tests/test_backlog_status.py` (text/json/missing-file coverage);
  - `acceptance_toolchain_self_check.sh` unit-tests bundle расширен:
    - `scripts/tests/test_backlog_status.py`;
  - `check_acceptance_self_check_test_bundle_sync.py` required modules обновлён
    новым test marker;
  - `test_acceptance_toolchain_self_check_script.py` обновлён проверкой
    присутствия `test_backlog_status.py` в self-check bundle;
  - runbook и acceptance map обновлены:
    - preflight command `uv run python scripts/backlog_status.py --json`;
    - operator snapshot note про JSON mode.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_check_backlog_status_json_contract.py scripts/tests/test_backlog_status.py scripts/tests/test_check_acceptance_self_check_test_bundle_sync.py scripts/tests/test_acceptance_toolchain_self_check_script.py -q`
    -> `11 passed`;
  - `uv run python scripts/check_backlog_status_json_contract.py` -> `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `46 passed`, `ok=16 failed=0`.

96. `P2` Backlog Status Artifact Lifecycle Hardening
- Status: `done`
- Scope:
  - добавить snapshot artifact export для backlog status (`latest + timestamped`);
  - покрыть artifact exporter автотестами и включить в self-check test bundle;
  - зафиксировать operator usage в runbook и acceptance automation map.
- Progress:
  - добавлен exporter:
    - `scripts/backlog_status_artifact.py`;
  - exporter формирует:
    - `docs/ops/backlog-status/latest.json`,
    - `docs/ops/backlog-status/backlog-status-<timestamp>.json`;
  - добавлен test module:
    - `scripts/tests/test_backlog_status_artifact.py`;
  - self-check unit-tests bundle расширен:
    - `scripts/tests/test_backlog_status_artifact.py`;
  - `check_acceptance_self_check_test_bundle_sync.py` required modules обновлён
    новым test marker;
  - runbook preflight обновлён командой:
    - `uv run python scripts/backlog_status_artifact.py`;
  - acceptance automation map дополнен секцией artifact snapshot script.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_backlog_status_artifact.py scripts/tests/test_backlog_status_hygiene.py scripts/tests/test_check_backlog_status_artifacts_index.py scripts/tests/test_check_acceptance_self_check_test_bundle_sync.py scripts/tests/test_acceptance_toolchain_self_check_script.py -q`
    -> `12 passed`;
  - `uv run python scripts/backlog_status_artifact.py` -> timestamped artifact + latest updated;
  - `uv run python scripts/backlog_status_hygiene.py --keep 50` -> `INDEX.md` generated;
  - `uv run python scripts/check_backlog_status_artifacts_index.py` -> `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `52 passed`, `ok=17 failed=0`.

97. `P2` Backlog Status Drift Guard Integration
- Status: `done`
- Scope:
  - добавить drift-guard между источниками backlog состояния
    (markdown validator/status parser/artifacts/ops summary);
  - зафиксировать operator-visible сигнал drift в acceptance ops summary;
  - закрепить guardrail coverage в self-check/docs.
- Progress:
  - `acceptance_ops_summary.py` расширен backlog status полями:
    - `backlog_status_latest_exists`,
    - `backlog_status_artifacts_total`,
    - `backlog_tasks_total`,
    - `backlog_in_progress_total`,
    - `backlog_focus_refs_total`,
    - `backlog_done_total`,
    - `backlog_todo_total`;
  - добавлен test module:
    - `scripts/tests/test_acceptance_ops_summary.py`;
  - self-check unit-tests bundle расширен новым test module marker;
  - в self-check добавлен guard step:
    - `backlog status artifacts index check`
    - (`scripts/check_backlog_status_artifacts_index.py`);
  - docs/runbook sync обновлены для backlog status artifact lifecycle:
    - `docs/ops/acceptance-automation-map.md`,
    - `docs/LOCAL_PROD_RUNBOOK.md`.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_check_backlog_status_drift.py scripts/tests/test_acceptance_ops_summary.py scripts/tests/test_check_acceptance_docs_navigation.py scripts/tests/test_check_acceptance_guardrails_sync.py scripts/tests/test_check_acceptance_self_check_test_bundle_sync.py scripts/tests/test_acceptance_toolchain_self_check_script.py -q`
    -> `12 passed`;
  - `uv run python scripts/check_backlog_status_drift.py` -> `ok`;
  - `uv run python scripts/check_backlog_status_artifacts_index.py` -> `ok`;
  - `uv run python scripts/acceptance_ops_summary.py --json` -> includes backlog snapshot fields;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `54 passed`, `ok=18 failed=0`.

98. `P2` Backlog Status Drift Signal In Ops Summary
- Status: `done`
- Scope:
  - добавить в `acceptance_ops_summary` явный drift signal
    (live backlog status vs latest backlog artifact);
  - вывести signal в human/json output для ежедневного operator snapshot;
  - закрепить coverage в self-check/tests и docs map.
- Progress:
  - `acceptance_ops_summary.py` расширен drift signal полями:
    - `backlog_drift_detected`,
    - `backlog_drift_reason`;
  - drift signal вычисляется по сравнению live status (`backlog_status.py --json`)
    и `docs/ops/backlog-status/latest.json` по ключам:
    - `tasks_total`, `status_counts`, `in_progress`, `focus_refs`;
  - добавлен test module:
    - `scripts/tests/test_check_backlog_status_drift.py`;
  - `acceptance_ops_summary` tests расширены:
    - in-sync case (`False/in_sync`),
    - mismatch case (`True/live_vs_artifact_mismatch`);
  - self-check flow расширен шагом:
    - `backlog status drift check` (`scripts/check_backlog_status_drift.py`);
  - self-check pytest bundle расширен new module markers:
    - `scripts/tests/test_check_backlog_status_drift.py`;
  - docs/runbook sync обновлены marker-ами:
    - `scripts/check_backlog_status_drift.py`.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_check_backlog_status_drift.py scripts/tests/test_acceptance_ops_summary.py scripts/tests/test_check_acceptance_docs_navigation.py scripts/tests/test_check_acceptance_guardrails_sync.py scripts/tests/test_check_acceptance_self_check_test_bundle_sync.py scripts/tests/test_acceptance_toolchain_self_check_script.py -q`
    -> `12 passed`;
  - `uv run python scripts/check_backlog_status_drift.py` -> `ok`;
  - `uv run python scripts/acceptance_ops_summary.py --json` -> includes `backlog_drift_detected/backlog_drift_reason`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `55 passed`, `ok=18 failed=0`.

99. `P2` Backlog Status Auto-Refresh Guidance Integration
- Status: `done`
- Scope:
  - зафиксировать operator-friendly последовательность:
    `backlog update -> backlog_status_artifact -> backlog_status_hygiene -> drift check`;
  - добавить concise troubleshooting notes для drift сигналов в runbook;
  - закрепить guidance markers через docs/navigation sync.
- Progress:
  - в runbook добавлен явный auto-refresh sequence:
    - `uv run python scripts/backlog_status_artifact.py`
    - `uv run python scripts/backlog_status_hygiene.py --keep 50`
    - `uv run python scripts/check_backlog_status_drift.py`;
  - добавлен runbook блок `Backlog status auto-refresh playbook`;
  - добавлен runbook блок `Backlog status drift troubleshooting` с reason-oriented steps;
  - в acceptance automation map добавлен backlog auto-refresh sequence;
  - docs-navigation checker закреплён новыми guidance markers:
    - `uv run python scripts/backlog_status_artifact.py`
    - `uv run python scripts/backlog_status_hygiene.py --keep 50`;
  - runbook sanity checker расширен маркерами artifact/hygiene команд.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_check_acceptance_docs_navigation.py scripts/tests/test_check_acceptance_runbook_sanity_sync.py scripts/tests/test_acceptance_ops_summary.py scripts/tests/test_check_backlog_status_drift.py scripts/tests/test_check_acceptance_self_check_test_bundle_sync.py scripts/tests/test_acceptance_toolchain_self_check_script.py -q`
    -> `13 passed`;
  - `uv run python scripts/check_acceptance_docs_navigation.py` -> `ok`;
  - `uv run python scripts/check_acceptance_runbook_sanity_sync.py` -> `ok`;
  - `uv run python scripts/check_backlog_status_drift.py` -> `ok` (after refresh sequence);
  - `./scripts/acceptance_toolchain_self_check.sh` -> `55 passed`, `ok=18 failed=0`.

## Execution Wave: Master Plan Delivery (fixed scope)

100. `P1` Phase A Closure Checklist (Runtime Stabilization)
- Status: `done`
- Scope:
  - сверить текущий runtime/acceptance state против `13-master-implementation-plan.md` (Phase A exit criteria);
  - собрать gap-list (если есть) и закрыть только критичные блокеры стабильности;
  - зафиксировать evidence в runbook/docs.
- Progress:
  - добавлен closure документ:
    - `docs/ops/phase-a-closure-checklist.md`;
  - в runbook добавлена ссылка на Phase A closure checklist;
  - runtime stabilization evidence зафиксирован:
    - `/api/health` -> `status=ok`,
    - `check_runtime_parity.sh` -> `runtime parity check passed`,
    - `acceptance_toolchain_self_check.sh` -> green;
  - устранён false-positive drift в self-check:
    - добавлен шаг `backlog status auto-refresh` перед drift check.
- Validation (April 10, 2026):
  - `curl -fsS http://localhost:${HIVE_CORE_PORT:-8787}/api/health` -> `status=ok`;
  - `./scripts/check_runtime_parity.sh` -> `runtime parity check passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=19 failed=0`.

101. `P1` Phase B Closure Checklist (Autonomous Pipeline Determinism)
- Status: `done`
- Scope:
  - верифицировать deterministic stage transitions/retries/escalation;
  - подтвердить PR-ready reports и reproducible terminal states по run samples.
- Progress:
  - добавлен closure документ:
    - `docs/ops/phase-b-closure-checklist.md`;
  - подтверждён deterministic API contract автономного pipeline:
    - `uv run pytest core/framework/server/tests/test_api.py -k "pipeline_" -q` -> `27 passed`;
    - `uv run pytest core/framework/server/tests/test_api.py -k "escalates_on_review_after_retries or evaluate_endpoint_uses_checks_and_updates_report or run_until_terminal_endpoint or execute_next_endpoint or run_cycle_reports_terminal_and_pr_ready" -q` -> `5 passed`;
  - подтверждён runtime/acceptance green contour после pipeline checks:
    - `./scripts/check_runtime_parity.sh` -> `runtime parity check passed`;
    - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=19 failed=0`.
- Validation (April 10, 2026):
  - `uv run pytest core/framework/server/tests/test_api.py -k "pipeline_" -q` -> `27 passed, 106 deselected`;
  - `uv run pytest core/framework/server/tests/test_api.py -k "escalates_on_review_after_retries or evaluate_endpoint_uses_checks_and_updates_report or run_until_terminal_endpoint or execute_next_endpoint or run_cycle_reports_terminal_and_pr_ready" -q` -> `5 passed, 128 deselected`;
  - `./scripts/check_runtime_parity.sh` -> `runtime parity check passed`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=19 failed=0`.

102. `P1` Phase C Closure Checklist (MCP Access + Credential Policy)
- Status: `done`
- Scope:
  - ревалидировать required MCP stack health;
  - подтвердить explicit diagnostics/no-silent-fail policy.
- Progress:
  - добавлен closure документ:
    - `docs/ops/phase-c-closure-checklist.md`;
  - подтверждён health required MCP stack:
    - `uv run python scripts/mcp_health_summary.py --since-minutes 30` -> `status: ok` (`5/5`);
    - `./scripts/verify_access_stack.sh` -> `GitHub/Telegram/Google/Redis/Postgres/refresher` = `OK`;
  - устранена деградация Google access token:
    - pre-check: `google HTTP 400`;
    - remediation: `./scripts/google_token_auto_refresh.sh` (`Refresh success`, `.env` updated);
    - post-check: `google HTTP 200`;
  - подтверждён runtime signal для `files-tools`:
    - выполнен probe session load (`examples/templates/deep_research_agent`);
    - в `docker compose logs` зафиксированы строки:
      `Connected to MCP server 'files-tools'` + `Discovered 6 tools from 'files-tools'`;
    - post-check: `files_tools_runtime` -> `ok`.
  - explicit diagnostics/no-silent-fail подтверждены инструментально:
    - `scripts/mcp_health_summary.py` возвращает per-check status/code/detail + общий `status`;
    - `scripts/verify_access_stack.sh` возвращает явные `[OK]/[WARN]` сигналы по access stack;
    - `scripts/audit_mcp_credentials.py` показывает set/missing env vars без скрытых пропусков.
- Validation (April 10, 2026):
  - `uv run python scripts/mcp_health_summary.py --since-minutes 30` -> `status: ok`, `ok: 5/5`;
  - `./scripts/verify_access_stack.sh` -> all target checks `OK`;
  - `./scripts/google_token_auto_refresh.sh` -> `Refresh success. expires_in=3599`;
  - `docker compose logs --since=10m hive-core | rg "files-tools|Connected to MCP server|Discovered .* tools"` -> runtime registration evidence present.

103. `P1` Phase D Closure Checklist (Ops Recovery Readiness)
- Status: `done`
- Scope:
  - подтвердить backup/restore drills, stale remediation, scheduler ops routine;
  - закрепить on-call troubleshooting flow.
- Progress:
  - добавлен closure документ:
    - `docs/ops/phase-d-closure-checklist.md`;
  - выявлен и закрыт ops-риск по stale autonomous runs:
    - pre-check: `stuck_runs=223`, `no_progress_projects=223`;
    - apply remediation: `HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=false HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=true HIVE_AUTONOMOUS_REMEDIATE_MAX_RUNS=500 ./scripts/autonomous_remediate_stale_runs.sh`;
    - remediation result: `selected_total=223`, `remediated_total=223`;
    - post-check: `./scripts/autonomous_ops_health_check.sh` -> `stuck_runs=0`, `no_progress_projects=0`.
  - подтверждён recovery контур:
    - `./scripts/autonomous_ops_drill.sh` -> `Drill summary: ok=5 failed=0`;
    - backup + restore dry-run выполняются в drill автоматически.
  - scheduler ops routine и troubleshooting закреплены:
    - launchd wrappers install/status/uninstall проверены;
    - в runbook добавлен explicit fallback на manual cadence при host-level
      `Operation not permitted` для launchd в текущем repo path.
- Validation (April 10, 2026):
  - `./scripts/autonomous_ops_health_check.sh` -> `ok`;
  - `./scripts/autonomous_ops_drill.sh` -> `ok=5 failed=0`;
  - `./scripts/acceptance_scheduler_snapshot.sh` -> scheduler snapshot + logs/troubleshooting visible;
  - `./scripts/status_autonomous_loop_launchd.sh` / `status_acceptance_gate_launchd.sh` / `status_acceptance_weekly_launchd.sh`
    -> deterministic state (`not-installed` after explicit uninstall fallback path).

104. `P1` Phase E Closure Checklist (Governance + Operator UX)
- Status: `done`
- Scope:
  - финализировать governance/UX/docs coverage against master-plan DoD;
  - сформировать final go-live acceptance pack.
- Progress:
  - добавлен closure документ:
    - `docs/ops/phase-e-closure-checklist.md`;
  - собран финальный operator package:
    - `docs/ops/final-go-live-acceptance-pack.md`;
  - runbook синхронизирован с фазовыми closure-документами (`A`..`E`) и final acceptance pack;
  - governance/guardrails контур подтверждён:
    - `validate_backlog_markdown.py` -> terminal completion mode (`in_progress=[]`, `focus_refs=[]`);
    - `check_backlog_status_drift.py` -> `in_sync`;
    - `acceptance_toolchain_self_check.sh` -> `ok=19 failed=0`.
- Validation (April 10, 2026):
  - `uv run python scripts/validate_backlog_markdown.py` -> `tasks_total=104 in_progress=[] focus_refs=[]`;
  - `uv run python scripts/backlog_status.py --path docs/autonomous-factory/12-backlog-task-list.md` -> `done=104, in_progress=0, todo=0`;
  - `uv run python scripts/mcp_health_summary.py --since-minutes 30` -> `status=ok (5/5)`;
  - `./scripts/autonomous_ops_health_check.sh` -> `ok`;
  - `./scripts/acceptance_toolchain_self_check.sh` -> `Self-check summary: ok=19 failed=0`.
  - `HIVE_ACCEPTANCE_SKIP_CHECKLIST=true ./scripts/autonomous_acceptance_gate.sh` -> `Acceptance summary: ok=12 failed=0`.

105. `P1` Scheduler Fallback Hardening (cron wrappers + docs parity)
- Status: `done`
- Scope:
  - закрыть gap persistent scheduler на хостах, где launchd блокирует repo scripts (`Operation not permitted`);
  - добавить managed cron wrappers для acceptance gate, weekly maintenance, autonomous loop;
  - синхронизировать runbook/automation map/scheduler snapshot под dual-mode scheduler (launchd + cron).
- Progress:
  - добавлены cron wrappers:
    - acceptance gate: `install/status/uninstall_acceptance_gate_cron.sh`;
    - weekly maintenance: `install/status/uninstall_acceptance_weekly_cron.sh`;
    - autonomous loop: `install/status/uninstall_autonomous_loop_cron.sh`;
    - shared helper: `scripts/_cron_job_lib.sh` (safe upsert/remove/status by marker).
  - `scripts/acceptance_scheduler_snapshot.sh` расширен:
    - показывает status для launchd и cron (`gate`, `weekly`, `autonomous loop`);
    - добавлены tails для cron логов.
  - `scripts/acceptance_toolchain_self_check.sh` расширен shell-syntax coverage на новые cron scripts.
  - docs синхронизированы:
    - `docs/LOCAL_PROD_RUNBOOK.md` (install/status/uninstall cron wrappers + troubleshooting fallback path);
    - `docs/ops/acceptance-automation-map.md` (scheduler wrappers + cadence guidance).
  - `scripts/acceptance_ops_summary.py` расширен scheduler status полями:
    - `scheduler_acceptance_gate_launchd|cron`,
    - `scheduler_acceptance_weekly_launchd|cron`,
    - `scheduler_autonomous_loop_launchd|cron`.
- Validation (April 10, 2026):
  - `uv run python scripts/backlog_status.py --path docs/autonomous-factory/12-backlog-task-list.md` -> `done=105, in_progress=0, todo=0`;
  - `uv run python scripts/validate_backlog_markdown.py` -> `tasks_total=105 in_progress=[] focus_refs=[]`;
  - `./scripts/acceptance_scheduler_snapshot.sh` -> launchd+cron status blocks rendered;
  - `./scripts/acceptance_toolchain_self_check.sh` -> pass.

106. `P1` Container-Native Scheduler Sidecar (docker compose)
- Status: `done`
- Scope:
  - устранить зависимость от host `launchd/cron` для автономного цикла;
  - добавить persistent scheduler service в `docker compose`;
  - обеспечить наблюдаемость через `docker compose logs` и runbook.
- Progress:
  - добавлен daemon:
    - `scripts/autonomous_scheduler_daemon.py`
    - выполняет:
      - periodic `POST /api/autonomous/loop/run-cycle/report`;
      - periodic acceptance probe (`GET /api/health` + `GET /api/autonomous/ops/status`);
      - structured JSON logs + graceful shutdown on `SIGTERM`.
  - в `docker-compose.yml` добавлен сервис `hive-scheduler`:
    - image: `python:3.11-slim`;
    - mounts `./scripts:/scripts:ro`;
    - env-driven intervals/projects;
    - depends on `hive-core` healthy.
  - docs обновлены:
    - `docs/LOCAL_PROD_RUNBOOK.md` (docker-native scheduler section + env knobs);
    - `docs/ops/acceptance-automation-map.md` (sidecar as preferred persistent scheduler path).
  - добавлены unit tests:
    - `scripts/tests/test_autonomous_scheduler_daemon.py`;
    - self-check bundle и guardrail sync обновлены.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_autonomous_scheduler_daemon.py -q` -> pass;
  - `docker compose up -d hive-scheduler` -> service started;
  - `docker compose logs --since=2m hive-scheduler` -> periodic `autonomous_tick_ok` records present.

107. `P1` Container-Only Portability Baseline (cross-machine)
- Status: `done`
- Scope:
  - зафиксировать режим эксплуатации "only docker services" как baseline;
  - убрать зависимость от host scheduler-ов в operational контуре;
  - добавить health contract для `hive-scheduler`.
- Progress:
  - `hive-scheduler` усилен heartbeat/state contract:
    - state file: `HIVE_SCHEDULER_STATE_PATH` (default `/tmp/hive_scheduler_state.json`);
    - periodic heartbeat: `HIVE_SCHEDULER_HEARTBEAT_INTERVAL_SECONDS` (default `5`);
    - state содержит `updated_at`, counters, last autonomous/acceptance results.
  - в `docker-compose.yml` добавлен healthcheck для `hive-scheduler`:
    - проверяет freshness state (`HIVE_SCHEDULER_HEALTH_STALE_SECONDS`, default `180`).
  - runbook обновлён под container-only baseline:
    - explicit sequence отключения host launchd/cron wrappers;
    - запуск только через `docker compose up -d hive-scheduler`.
  - snapshot/ops summary учитывают docker scheduler status как primary signal.
- Validation (April 10, 2026):
  - `docker compose ps hive-scheduler` -> `Up ... (healthy)`;
  - `docker compose logs --since=6m hive-scheduler` -> repeated `autonomous_tick_ok`;
  - `uv run python scripts/acceptance_ops_summary.py --json` ->
    `scheduler_hive_scheduler_container=running`, host schedulers `not-installed`.

108. `P1` Scheduler Session Binding for Autonomous Execution
- Status: `done`
- Scope:
  - устранить ручную привязку session при каждом запуске автономного цикла;
  - поддержать project-level session routing прямо в docker scheduler.
- Progress:
  - `autonomous_scheduler_daemon.py` поддерживает:
    - `HIVE_SCHEDULER_SESSION_ID` (single session),
    - `HIVE_SCHEDULER_SESSION_ID_BY_PROJECT_JSON` (map project->session, preferred).
  - payload `run-cycle/report` теперь передаёт `session_id_by_project` или `session_id`;
  - `docker-compose.yml` обновлён новыми env knobs для scheduler service;
  - runbook обновлён (env reference);
  - добавлен unit-test на приоритет `session_id_by_project` over `session_id`.
- Validation (April 10, 2026):
  - `uv run pytest scripts/tests/test_autonomous_scheduler_daemon.py -q` -> pass;
  - `docker compose up -d --force-recreate hive-scheduler` -> healthy;
  - `docker compose logs --since=3m hive-scheduler` -> `scheduler_started` + `autonomous_tick_ok`.

## Execution Wave: Upstream Integration (Safe Merge, No Regressions)

109. `P0` Upstream Security Backport: `safe_eval`
- Status: `done`
- Scope:
  - интегрировать upstream security fixes:
    - bound `ast.Pow`,
    - timeout enforcement,
    - host alarm state preservation;
  - сохранить совместимость с текущим runtime и тестами проекта.
- Done when:
  - security patches в `core/framework/graph/safe_eval.py` применены;
  - `core/tests/test_safe_eval.py` и локальный regression suite зеленые;
  - acceptance/self-check без деградации.
- Progress:
  - backport применён в `core/framework/graph/safe_eval.py`:
    - `ast.Pow` переведён на bounded `_safe_pow` (limit exponent/result size);
    - добавлен timeout guard (`timeout_ms`, default `100ms`);
    - добавлен alarm-safe execution context с сохранением host timer state.
  - расширены тесты `core/tests/test_safe_eval.py`:
    - power guard cases;
    - timeout behavior and alarm restore/preserve cases.
  - Validation (April 10, 2026):
    - `uv run --active pytest core/tests/test_safe_eval.py -q` -> `122 passed`;
    - `uv run --active pytest core/tests/test_safe_eval.py -k "power or timeout" -q` -> `10 passed`.

110. `P0` Upstream Core Stability Patch: `litellm` read-only FS crash guard
- Status: `done`
- Scope:
  - портировать fix `d8712ceb` для `_dump_failed_request` в текущий `litellm.py`;
  - убедиться, что текущая кастомная маршрутизация/профили не ломаются.
- Done when:
  - при read-only/permission error runtime не падает;
  - LLM routing и текущие model profiles проходят smoke.
- Progress:
  - в `core/framework/llm/litellm.py` `_dump_failed_request` обёрнут в `try/except OSError`;
  - при filesystem write error теперь логируется warning и возвращается `"log_write_failed"` вместо crash;
  - добавлены unit-тесты в `core/tests/test_litellm_provider.py`:
    - success path dump creation;
    - `OSError` path возвращает `"log_write_failed"`.
  - Validation (April 10, 2026):
    - `uv run --active pytest core/tests/test_litellm_provider.py -q` -> `96 passed`;
    - `uv run --active ruff check core/framework/llm/litellm.py core/tests/test_litellm_provider.py` -> `All checks passed`.

111. `P1` Optional Tooling Integration: W&B (`wandb_tool`) behind explicit enablement
- Status: `done`
- Scope:
  - добавить upstream W&B tool и credential adapter;
  - включение только через явный env/config (disabled by default).
- Done when:
  - tool доступен при enable flag;
  - default runtime без W&B остается неизменным.
- Progress:
  - добавлены upstream модули:
    - `tools/src/aden_tools/credentials/wandb.py`,
    - `tools/src/aden_tools/tools/wandb_tool/*`,
    - `tools/tests/tools/test_wandb_tool.py`;
  - зарегистрирован `register_wandb(...)` в unverified tool registry;
  - credential registry обновлён (`WANDB_CREDENTIALS` в `CREDENTIAL_SPECS`/`__all__`);
  - enable contract:
    - default runtime unchanged (`include_unverified=False` -> `wandb_*` tools absent);
    - explicit enable via unverified-tools profile (`INCLUDE_UNVERIFIED_TOOLS=true`).
  - Validation (April 10, 2026):
    - `uv run --active pytest tests/tools/test_wandb_tool.py -q` -> `18 passed`;
    - `uv run --active pytest tests/integrations/test_registration.py -q` -> `299 passed, 1 skipped`;
    - `uv run --active pytest tests/integrations/test_spec_conformance.py -q` -> `1381 passed, 2 skipped`;
    - `uv run --active ruff check ...` (modified W&B files) -> `All checks passed`;
    - registration smoke:
      - `include_unverified=False` -> `verified_contains_wandb=False`;
      - `include_unverified=True` -> `unverified_contains_wandb=True`.

112. `P1` Queen Memory/Reflection Upstream Delta Audit + Compatibility Design
- Status: `done`
- Scope:
  - разобрать upstream wave `6637bc8d..19469ff4` по memory/reflection;
  - подготовить compatibility план для нашего project/autonomous/telegram стека.
- Done when:
  - есть документ merge strategy с рисками/rollback;
  - определен целевой совместимый набор изменений.
- Progress:
  - выполнен file-level delta audit по upstream range `6637bc8d..19469ff4`:
    - `queen_memory_v2`, `recall_selector`, `reflection_agent`,
      `queen_orchestrator`, `routes_execution`, `session_manager`, related tests;
  - выявлены конфликтные зоны с локальными расширениями:
    - project-aware session model,
    - autonomous pipeline hooks,
    - telegram bridge runtime stability,
    - worker handoff continuity;
  - оформлен compatibility design документ:
    - `docs/autonomous-factory/14-upstream-memory-reflection-compatibility-plan.md`;
    - включает risk matrix, phased merge strategy (A/B/C), rollback plan, and acceptance gates;
  - определен совместимый target-set для item `113`:
    - merge only safe/controlled subset, defer full global-only memory cutover.

113. `P1` Controlled Merge: `session_manager` + queen runtime hotspots
- Status: `done`
- Scope:
  - применить совместимые части upstream в:
    - `core/framework/server/session_manager.py`,
    - связанные queen runtime узлы;
  - не допустить regressions в project-aware sessions и worker handoff.
- Done when:
  - API/tests по sessions/projects/worker_handoff зеленые;
  - Telegram bridge сценарии стабильны.
- Progress:
  - applied controlled merge subset from upstream memory/reflection wave:
    - `routes_execution`: `CLIENT_INPUT_RECEIVED` publish moved before queen `inject_event` (deterministic recall timing);
    - `queen_orchestrator`: added recall refresh on user input + initial global recall seeding on session start trigger;
    - `reflection_agent`: added object-style tool-call parsing compatibility for litellm responses;
    - `reflection_agent`: added `run_shutdown_reflection(...)` helper;
    - `session_manager`: added `queen_dir` tracking + guarded fire-and-forget shutdown reflection with strong task references.
  - intentionally preserved local hybrid memory architecture (no destructive colony-memory removal in this wave).
  - Validation (April 10, 2026):
    - `uv run --active pytest core/tests/test_queen_memory.py -q` -> `39 passed`;
    - `uv run --active pytest core/tests/test_session_manager_worker_handoff.py -q` -> `9 passed`;
    - `uv run --active pytest core/framework/server/tests/test_api.py -k "sessions or autonomous or execution_template or telegram_bridge_status_endpoint or health" -q` -> `51 passed`;
    - `uv run --active pytest core/framework/server/tests/test_telegram_bridge.py -q` -> `9 passed`;
    - `uv run --active ruff check core/framework/server/routes_execution.py core/framework/server/queen_orchestrator.py core/framework/agents/queen/reflection_agent.py core/framework/server/session_manager.py` -> `All checks passed`.

114. `P1` Frontend Reconciliation: Workspace Upstream vs Local Project UX
- Status: `done`
- Scope:
  - аккуратно примирить upstream изменения `workspace.tsx` с нашими project/autonomous controls;
  - сохранить Telegram/Web parity по ключевым действиям.
- Done when:
  - текущие project/autonomous UI controls сохранены;
  - новые upstream UI fixes интегрированы без потери функционала.
- Progress:
  - выполнен reconciliation-аудит по `workspace.tsx`: upstream delta в основном удаляет local tab UX и не совместим с нашим project/autonomous control-plane;
  - принят controlled-merge подход: сохранить локальные controls и забрать безопасные UX hardening фиксы;
  - applied UI hardening в `core/frontend/src/pages/workspace.tsx`:
    - `NewTabPopover` position now viewport-clamped (no horizontal overflow),
    - auto-reposition on `resize` and `scroll`,
    - removed debug `console.log` noise and unused `activeWorker` prop;
  - подтверждено, что local project/autonomous/telegram-oriented workspace controls сохранены без функциональной деградации.
  - Validation (April 10, 2026):
    - `npm run build` (`core/frontend`) -> success.

115. `P0` Full Regression Gate After Upstream Wave
- Status: `done`
- Scope:
  - прогнать:
    - targeted unit tests,
    - API pipeline tests,
    - acceptance toolchain self-check,
    - runtime parity;
  - зафиксировать evidence в ops docs.
- Done when:
  - `acceptance_toolchain_self_check.sh` green;
  - `check_runtime_parity.sh` green;
  - `backlog drift` in sync.
- Progress:
  - regression gate completed after upstream integration wave:
    - targeted unit/API/Telegram tests green (memory/session/worker-handoff/autonomous scope),
    - acceptance toolchain self-check passed,
    - runtime parity check passed,
    - backlog status drift/consistency checks in sync.
  - Validation (April 10, 2026):
    - `./scripts/acceptance_toolchain_self_check.sh` -> `ok=20 failed=0` (self-check summary);
    - `./scripts/check_runtime_parity.sh` -> `runtime parity check passed`;
    - `uv run python scripts/check_backlog_status_consistency.py` -> in sync (`in_progress=[115]` at run time).

116. `P1` Upstream Sync Governance (cadence + guardrails)
- Status: `done`
- Scope:
  - закрепить повторяемый процесс апстрим-интеграции волнами:
    - security-first,
    - core-stability,
    - optional tooling,
    - high-risk refactors;
  - добавить чеклист “do-not-break local factory”.
- Done when:
  - в docs есть операционный runbook апстрим-синка;
  - следующие апдейты выполняются без ad-hoc merge.
- Progress:
  - добавлен governance runbook:
    - `docs/autonomous-factory/15-upstream-sync-governance.md`;
  - runbook фиксирует:
    - sync cadence,
    - mandatory wave order,
    - pre-flight + regression gates,
    - do-not-break local factory guardrails,
    - rollback protocol,
    - standard wave execution template;
  - обновлен `docs/autonomous-factory/README.md` c включением:
    - `13-master-implementation-plan`,
    - `14-upstream-memory-reflection-compatibility-plan`,
    - `15-upstream-sync-governance`.
  - добавлены automation wrappers для повторяемого выполнения governance gate:
    - `scripts/upstream_sync_preflight.sh`
    - `scripts/upstream_sync_regression_gate.sh`
  - runbook обновлен ссылками на wrapper-команды.
  - Validation (April 10, 2026):
    - `./scripts/upstream_sync_preflight.sh` -> pass;
    - `./scripts/upstream_sync_regression_gate.sh` -> pass;
    - `uv run python scripts/validate_backlog_markdown.py` -> pass;
    - `uv run python scripts/backlog_status.py --path docs/autonomous-factory/12-backlog-task-list.md` -> `in_progress=[]`, `done=116`.

## Execution Wave: Upstream Continuation (Delta Buckets A/B/C)

117. `P0` Upstream Delta Inventory + Risk Bucketing (Wave 2 kickoff)
- Status: `done`
- Scope:
  - зафиксировать текущий upstream delta после закрытия `109..116`;
  - разделить remaining изменения на low/medium/high-risk buckets;
  - подготовить последовательность выполнения wave `117..121`.
- Done when:
  - есть отдельный inventory doc с file buckets и guardrails;
  - новый execution wave оформлен в backlog.
- Progress:
  - выполнен snapshot:
    - `git rev-list --left-right --count HEAD...origin/main` -> `0 25`;
    - `git diff --name-status HEAD..origin/main` / `--numstat` для полного file-level delta;
  - подготовлен inventory документ:
    - `docs/autonomous-factory/16-upstream-wave2-delta-inventory.md`;
  - в документе зафиксированы:
    - уже интегрированные изменения из `109..116`,
    - remaining buckets `A/B/C`,
    - execution sequence и guardrails для wave 2.

118. `P1` Controlled Merge Batch A: Docs + Meta Sync
- Status: `done`
- Scope:
  - интегрировать low-risk upstream delta без runtime-поведения:
    - `.gitignore`,
    - `README.md`,
    - `core/framework/runtime/README.md`,
    - `docs/browser-extension-setup.html`,
    - `docs/configuration.md`,
    - `docs/developer-guide.md`,
    - `docs/environment-setup.md`.
- Done when:
  - все Bucket A файлы синхронизированы с upstream в безопасной форме;
  - docs-навигация/базовые sanity-checks проходят.
- Progress:
  - синхронизированы upstream-правки по Bucket A файлам (copy UX в browser-extension setup, storage path defaults в docs, runtime/readme wording, `.coverage` ignore);
  - обновлен `docs/autonomous-factory/README.md`:
    - добавлен `16-upstream-wave2-delta-inventory.md`.
  - Validation (April 10, 2026):
    - `uv run python scripts/check_acceptance_docs_navigation.py` -> pass;
    - `uv run python scripts/validate_backlog_markdown.py` -> pass;
    - `uv run python scripts/backlog_status.py --path docs/autonomous-factory/12-backlog-task-list.md` -> `in_progress=[118]` at run time.

119. `P1` Controlled Merge Batch B: Runtime/Event Flow Deltas
- Status: `done`
- Scope:
  - применить medium-risk изменения из Bucket B:
    - runtime/event-bus/graph/recall paths;
  - обеспечить совместимость с project-scoped sessions, autonomous pipeline и telegram bridge.
- Done when:
  - controlled merge выполнен по file-slices с targeted tests после каждого slice;
  - нет regressions по API/Telegram/autonomous маршрутам.
- Progress:
  - runtime batch разбит на slices:
    - `B1`: graph/event bus surface (`graph/context.py`, `graph/executor.py`, `graph/worker_agent.py`, `tests/test_event_bus.py`);
    - `B2`: memory recall flow (`queen_memory_v2.py`, `recall_selector.py`, `tests/test_queen_memory.py`);
    - `B3`: lifecycle/runtime wiring (`agent_runtime.py`, `execution_stream.py`, `queen_lifecycle_tools.py`, `queen/nodes/__init__.py`).
  - `B1` стартован:
    - добавлен upstream test suite `core/tests/test_event_bus.py` (coverage shield для event-bus contracts);
    - validation:
      - `uv run --active pytest core/tests/test_event_bus.py -q` -> `46 passed`;
      - `uv run --active ruff check core/tests/test_event_bus.py` -> `All checks passed`;
    - code-removal часть B1 (`colony reflection` fields in `context/executor/worker_agent`) пока не применяется до завершения архитектурной оценки в item `120`.
  - `B2` partial merge (safe subset):
    - усилен `recall_selector.select_memories(...)`:
      - dual-format selection attempts (`json_schema` -> `json_object` fallback);
      - safe handling для empty/non-JSON payloads;
      - строгая фильтрация `selected_memories` до существующих string filenames;
    - добавлены тесты:
      - fallback path on empty payload;
      - invalid-memory entries filtering;
    - validation:
      - `uv run --active pytest core/tests/test_queen_memory.py -q` -> `41 passed`;
      - `uv run --active pytest core/tests/test_event_bus.py core/tests/test_queen_memory.py -q` -> `87 passed`;
      - `uv run --active ruff check core/framework/agents/queen/recall_selector.py core/tests/test_queen_memory.py` -> `All checks passed`.
  - `B3` decision:
    - upstream deltas in `agent_runtime/execution_stream/queen_lifecycle_tools/queen nodes` are tied to memory-architecture removals (`save_global_memory`, colony recall wiring);
    - destructive/removal subset explicitly deferred to item `120` as high-risk transition;
    - no unsafe B3 removals applied in item `119`.
  - Additional regression validation (April 10, 2026):
    - `uv run --active pytest core/framework/server/tests/test_api.py -k "sessions or autonomous or execution_template or telegram_bridge_status_endpoint or health" -q` -> `51 passed`;
    - `uv run --active pytest core/framework/server/tests/test_telegram_bridge.py -q` -> `9 passed`.

120. `P1` Controlled Merge Batch C: Memory Architecture Transition (High Risk)
- Status: `done`
- Scope:
  - оценить upstream memory simplification wave:
    - removal `queen_memory.py`/`queen_memory_tools.py`,
    - сопутствующее удаление colony-reflection wiring в graph/runtime слоях;
  - принять явное решение: defer, partial-flagged merge, или full cutover.
- Done when:
  - есть документированное архитектурное решение + rollback path;
  - high-risk path не попадает в production без explicit validation wave.
- Progress:
  - выделены high-risk blocks, напрямую связанные с upstream simplification:
    - deletion `queen_memory.py`, `queen_memory_tools.py`,
    - removal of colony reflection fields and runtime wiring,
    - removal of `save_global_memory` tool and related prompt instructions;
  - подтверждено, что эти изменения конфликтуют с текущим local autonomous-factory contract и требуют explicit architecture decision/rollback.
  - оформлено architecture decision + rollback документом:
    - `docs/autonomous-factory/17-memory-architecture-transition-decision.md`;
  - решение wave 2:
    - destructive memory removals deferred,
    - production-local профиль остается на validated hybrid compatibility path.

121. `P0` Full Regression Gate After Wave 2
- Status: `done`
- Scope:
  - прогнать полный regression gate после `118..120`:
    - acceptance self-check,
    - runtime parity,
    - backlog consistency,
    - targeted test matrix.
- Done when:
  - `./scripts/upstream_sync_regression_gate.sh` green;
  - backlog/status artifacts синхронизированы и заархивированы.
- Progress:
  - выполнен полный regression gate wave 2:
    - `./scripts/upstream_sync_regression_gate.sh` -> pass;
    - acceptance/self-check summary -> `ok=20 failed=0`;
    - runtime parity -> `runtime parity check passed`;
    - backlog consistency/drift/json contract/index checks -> all pass;
    - backlog-status artifacts refreshed (`docs/ops/backlog-status/latest.json` updated).

## Execution Wave: Upstream Automation Hardening

122. `P0` Wave Re-open + Delta Automation Scope
- Status: `done`
- Scope:
  - открыть новую bounded wave после terminal completion;
  - зафиксировать цель: убрать manual steps из upstream triage и contract drift.
- Done when:
  - в backlog есть новая wave с фиксированным scope и owner задачами.
- Progress:
  - открыта wave `122..126` с фокусом на automation guardrails для upstream sync.

123. `P1` Automated Upstream Delta Bucket Report
- Status: `done`
- Scope:
  - добавить script-level отчёт по `HEAD..origin/main` с bucket классификацией;
  - встроить отчёт в `upstream_sync_preflight.sh`.
- Done when:
  - preflight выводит bucketed delta summary без ручной классификации.
- Progress:
  - добавлен скрипт:
    - `scripts/upstream_delta_status.py`;
  - добавлены тесты:
    - `scripts/tests/test_upstream_delta_status.py` (`3 passed`);
  - preflight дополнен шагом:
    - `uv run python scripts/upstream_delta_status.py --base-ref HEAD --target-ref "${TARGET_REF}"`;
  - Validation (April 10, 2026):
    - `uv run --active pytest scripts/tests/test_upstream_delta_status.py -q` -> `3 passed`;
    - `uv run --active ruff check scripts/upstream_delta_status.py scripts/tests/test_upstream_delta_status.py` -> `All checks passed`.

124. `P1` Bucket Contract Sync Guardrail (Docs vs Script)
- Status: `done`
- Scope:
  - добавить check, что bucket карты в `16-upstream-wave2-delta-inventory.md` и automation script не расходятся.
- Done when:
  - preflight падает при drift между docs и code bucket mapping.
- Progress:
  - добавлен checker:
    - `scripts/check_upstream_bucket_contract_sync.py`;
  - добавлены тесты:
    - `scripts/tests/test_check_upstream_bucket_contract_sync.py` (`2 passed`);
  - preflight дополнен шагом:
    - `uv run python scripts/check_upstream_bucket_contract_sync.py`;
  - Validation (April 10, 2026):
    - `uv run --active pytest scripts/tests/test_check_upstream_bucket_contract_sync.py -q` -> `2 passed`;
    - `./scripts/upstream_sync_preflight.sh` -> pass (`bucket_a/b/c in sync`).

125. `P1` Unclassified Delta Triage Playbook
- Status: `done`
- Scope:
  - оформить операционный playbook для `other_unclassified` bucket;
  - определить правила эскалации и merge order по unclassified paths.
- Done when:
  - есть отдельный doc и ссылка в autonomous-factory index.
- Progress:
  - добавлен playbook:
    - `docs/autonomous-factory/18-unclassified-delta-triage-playbook.md`;
  - добавлена ссылка в:
    - `docs/autonomous-factory/README.md`.

126. `P0` Regression Gate + Status Sync (Automation Wave)
- Status: `done`
- Scope:
  - выполнить regression/sanity gate после задач `122..125`;
  - синхронизировать backlog status artifacts.
- Done when:
  - `upstream_sync_preflight.sh` и `upstream_sync_regression_gate.sh` green;
  - backlog валидаторы/consistency green и status artifacts обновлены.
- Progress:
  - `./scripts/upstream_sync_preflight.sh` -> pass;
  - bucket status + bucket contract sync выводятся и валидируются в preflight.
  - full wave gate completed:
    - `./scripts/upstream_sync_regression_gate.sh` -> pass;
    - acceptance self-check/runtime parity/backlog consistency -> pass;
    - backlog status artifacts updated (`docs/ops/backlog-status/latest.json` refreshed).

## Execution Wave: Unclassified Decision Governance

127. `P0` Wave Re-open: Unclassified Decision Coverage
- Status: `done`
- Scope:
  - открыть bounded wave для закрытия operational gap по `other_unclassified`;
  - сделать решение по unclassified paths машинно-проверяемым.
- Done when:
  - есть новая wave `127..130` с фиксированным scope.
- Progress:
  - wave `127..130` оформлена для decision governance по unclassified delta.

128. `P1` Decision Registry for Unclassified Paths
- Status: `done`
- Scope:
  - добавить machine-readable registry решений по каждому пути из `other_unclassified`.
- Done when:
  - для всех текущих unclassified путей есть `decision + rationale`.
- Progress:
  - добавлен registry:
    - `docs/ops/upstream-unclassified-decisions.json`;
  - покрыто `16/16` текущих unclassified paths;
  - текущий snapshot: `already-absorbed=16`, `defer=0`, `merge-now=0`;
  - добавлен operator doc:
    - `docs/autonomous-factory/19-unclassified-delta-decision-register.md`.

129. `P1` Enforce Decision Coverage in Preflight
- Status: `done`
- Scope:
  - добавить checker, который валидирует полноту decision coverage для `other_unclassified`;
  - встроить checker в preflight.
- Done when:
  - preflight падает при missing decision entry.
- Progress:
  - добавлен checker:
    - `scripts/check_unclassified_delta_decisions.py`;
  - добавлены тесты:
    - `scripts/tests/test_check_unclassified_delta_decisions.py`;
  - preflight дополнен шагом:
    - `uv run python scripts/check_unclassified_delta_decisions.py`;
  - Validation (April 11, 2026):
    - `uv run --active pytest scripts/tests/test_check_unclassified_delta_decisions.py scripts/tests/test_upstream_delta_status.py scripts/tests/test_check_upstream_bucket_contract_sync.py -q` -> `9 passed`;
    - `./scripts/upstream_sync_preflight.sh` -> pass (`covered_unclassified=16`).

130. `P0` Regression Gate + Status Sync (Decision Governance Wave)
- Status: `done`
- Scope:
  - выполнить полный regression gate после `127..129`;
  - синхронизировать backlog artifacts/status.
- Done when:
  - `upstream_sync_preflight.sh` и `upstream_sync_regression_gate.sh` green;
  - backlog/status consistency green.
- Progress:
  - `./scripts/upstream_sync_preflight.sh` -> pass (incl. bucket + decision coverage checks);
  - `./scripts/upstream_sync_regression_gate.sh` -> pass;
  - backlog status artifacts refreshed (`docs/ops/backlog-status/latest.json`).

## Execution Wave: Decision Evidence Hardening

131. `P1` Per-Path Decision Evidence Contract
- Status: `done`
- Scope:
  - перевести unclassified decision registry от минимального формата к evidence-based формату;
  - требовать для каждого path: `decision`, `rationale`, `backlog_items`, `validation`.
- Done when:
  - JSON registry содержит evidence-поля для каждого unclassified path;
  - checker валидирует новый контракт.
- Progress:
  - обновлен registry:
    - `docs/ops/upstream-unclassified-decisions.json` (16/16 paths с evidence);
  - обновлен checker:
    - `scripts/check_unclassified_delta_decisions.py` (contract validation для `backlog_items` и `validation`);
  - обновлены тесты checker:
    - `scripts/tests/test_check_unclassified_delta_decisions.py`.

132. `P1` Deterministic Markdown Report for Decision Registry
- Status: `done`
- Scope:
  - добавить генерацию markdown-отчета из decision registry + live unclassified set;
  - фиксировать path->decision snapshot в читаемом виде.
- Done when:
  - есть render script + отчет-файл под docs/ops.
- Progress:
  - добавлен renderer:
    - `scripts/render_unclassified_decision_report.py`;
  - добавлены тесты renderer:
    - `scripts/tests/test_render_unclassified_decision_report.py`;
  - сгенерирован отчет:
    - `docs/ops/upstream-unclassified-decisions.md`.

133. `P1` Enforce Report Sync in Preflight
- Status: `done`
- Scope:
  - встроить проверку синхронности markdown report с JSON registry в preflight.
- Done when:
  - preflight падает при report drift.
- Progress:
  - preflight дополнен шагом:
    - `uv run python scripts/render_unclassified_decision_report.py --check docs/ops/upstream-unclassified-decisions.md`;
  - playbook обновлен входными артефактами/командами:
    - `docs/autonomous-factory/18-unclassified-delta-triage-playbook.md`.

134. `P0` Regression Gate + Status Sync (Decision Evidence Wave)
- Status: `done`
- Scope:
  - выполнить full sanity/regression gate после `131..133`;
  - синхронизировать backlog artifacts.
- Done when:
  - `upstream_sync_preflight.sh` и `upstream_sync_regression_gate.sh` green;
  - tests/lint по новому decision/report контуру green.
- Progress:
  - Validation (April 11, 2026):
    - `uv run --active pytest scripts/tests/test_check_unclassified_delta_decisions.py scripts/tests/test_render_unclassified_decision_report.py scripts/tests/test_upstream_delta_status.py scripts/tests/test_check_upstream_bucket_contract_sync.py -q` -> `12 passed`;
    - `uv run --active ruff check scripts/check_unclassified_delta_decisions.py scripts/render_unclassified_decision_report.py scripts/tests/test_check_unclassified_delta_decisions.py scripts/tests/test_render_unclassified_decision_report.py scripts/tests/test_upstream_delta_status.py scripts/tests/test_check_upstream_bucket_contract_sync.py` -> `All checks passed`;
    - `./scripts/upstream_sync_preflight.sh` -> pass;
    - `./scripts/upstream_sync_regression_gate.sh` -> pass;
    - backlog status artifacts refreshed (`docs/ops/backlog-status/latest.json`).

## Execution Wave: Docker Build Performance Hardening

135. `P1` Docker Dependency Layer Caching + Two-Phase Workspace Sync
- Status: `done`
- Scope:
  - ускорить повторные сборки `hive-core` без изменения dependency contract;
  - отделить dependency install от workspace source copy, чтобы code-only changes не пересобирали весь dependency graph.
- Done when:
  - Dockerfile использует lockfile-first dependency layer;
  - повторная сборка использует кэш и проходит заметно быстрее.
- Progress:
  - Dockerfile обновлен:
    - добавлен syntax `docker/dockerfile:1.7`;
    - добавлены cache mounts для `npm` и `uv`;
    - добавлен двухфазный `uv sync`:
      - `uv sync --frozen --no-install-workspace` (deps layer),
      - `uv sync --frozen` после copy runtime sources;
    - добавлен `ENV UV_LINK_MODE=copy` для стабильного cache behavior в контейнере;
    - добавлен `COPY uv.lock` в dependency layer.
  - Валидация (April 11, 2026):
    - `HIVE_DOCKER_INSTALL_PLAYWRIGHT=0 docker compose build hive-core` -> pass;
    - последующая повторная сборка с кэшем -> pass (~7.5s end-to-end).

136. `P0` Runtime/Regression Validation + Runbook Sync (Docker Performance Wave)
- Status: `done`
- Scope:
  - подтвердить, что Docker performance hardening не ломает runtime/autonomous контур;
  - синхронизировать operator runbook и backlog status artifacts.
- Done when:
  - `hive-core` healthy после recreate;
  - runtime parity + upstream regression gate green;
  - runbook содержит обновленные guidance по build performance.
- Progress:
  - runbook обновлен:
    - `docs/LOCAL_PROD_RUNBOOK.md` (section `Build performance notes`);
  - runtime validation:
    - `docker compose up -d hive-core` -> healthy;
    - `curl /api/health` -> `status: ok`;
    - `./scripts/check_runtime_parity.sh` -> pass;
  - regression validation:
    - `./scripts/upstream_sync_preflight.sh` -> pass;
    - `./scripts/upstream_sync_regression_gate.sh` -> pass;
  - backlog status artifacts refreshed (`docs/ops/backlog-status/latest.json`).

## Execution Wave: Container-Only Sidecar Portability

137. `P1` Move Scheduler/Token Sidecars to Shared Hive Image
- Status: `done`
- Scope:
  - устранить зависимость sidecar-сервисов от host bind-mount `./scripts`;
  - запускать scheduler и google token refresher из того же runtime image, что и `hive-core`.
- Done when:
  - `hive-scheduler` и `google-token-refresher` стартуют из `${HIVE_CORE_IMAGE:-hive-hive-core}`;
  - в compose нет обязательного `./scripts:/scripts` mount для sidecars.
- Progress:
  - `Dockerfile` обновлен: `COPY scripts/ scripts/`;
  - `docker-compose.yml` обновлен:
    - `hive-scheduler` -> `image: ${HIVE_CORE_IMAGE:-hive-hive-core}`, command `uv run python scripts/autonomous_scheduler_daemon.py`;
    - `google-token-refresher` -> `image: ${HIVE_CORE_IMAGE:-hive-hive-core}`, command `uv run python scripts/google_token_refresher_daemon.py`;
    - sidecar bind-mount `./scripts` удален.

138. `P0` Sidecar Runtime Validation + Permission Hardening
- Status: `done`
- Scope:
  - проверить end-to-end запуск sidecars в контейнер-only режиме;
  - закрыть volume permission edge-case для token refresher.
- Done when:
  - `hive-core` healthy;
  - scheduler sidecar healthy и выполняет tick;
  - token refresher успешно делает refresh без permission errors.
- Progress:
  - `google-token-refresher` зафиксирован как root-run service в compose (`user: "0:0"`) для совместимости с legacy volume ownership;
  - для `google-token-refresher` отключен inherited image healthcheck (`disable: true`), чтобы убрать ложный probe на `:8787`;
  - Validation (April 11, 2026):
    - `HIVE_DOCKER_INSTALL_PLAYWRIGHT=0 docker compose up -d --build hive-core google-token-refresher hive-scheduler` -> pass;
    - `docker compose ps` -> `hive-core` healthy, `hive-scheduler` healthy, `google-token-refresher` running;
    - logs:
      - scheduler: `scheduler_started` + `autonomous_tick_ok`;
      - refresher: `refresh ok expires_in=3599`;
    - `./scripts/check_runtime_parity.sh` -> pass;
    - `./scripts/verify_access_stack.sh` -> pass for GitHub/Telegram/Redis/Postgres/refresher, Google refresh flow configured.

## Execution Wave: Playwright Runtime + Upstream Bucket A

139. `P0` Full Playwright Build/Runtime Validation (Non-Root)
- Status: `done`
- Scope:
  - подтвердить, что full build (`HIVE_DOCKER_INSTALL_PLAYWRIGHT=1`) реально даёт рабочий browser runtime в контейнере;
  - закрыть user-context mismatch (root install vs `hiveuser` runtime) для Playwright.
- Done when:
  - контейнер собирается и стартует в full mode;
  - Chromium успешно запускается под `hiveuser` и выполняет web navigation.
- Progress:
  - `Dockerfile` обновлен:
    - `ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`;
    - после `playwright install` применяется `chmod -R a+rX /ms-playwright`;
  - Validation (April 11, 2026):
    - `HIVE_DOCKER_INSTALL_PLAYWRIGHT=1 docker compose up -d --build hive-core google-token-refresher hive-scheduler` -> pass;
    - runtime smoke внутри контейнера:
      - `p.chromium.launch(headless=True)` -> pass;
      - `page.goto("https://example.com")` -> pass;
      - `title=Example Domain`.
  - runbook updated:
    - `docs/LOCAL_PROD_RUNBOOK.md` (`PLAYWRIGHT_BROWSERS_PATH` note).

140. `P1` Upstream Bucket A (Low-Risk) Safe Merge Closure + Regression
- Status: `done`
- Scope:
  - завершить текущий этап safe-merge по Bucket A без затрагивания medium/high-risk файлов;
  - прогнать regression/preflight после синхронизации low-risk слоя.
- Done when:
  - low-risk docs/config layer проверен и синхронизирован;
  - `upstream_sync_preflight.sh` и `upstream_sync_regression_gate.sh` green.
- Progress:
  - выполнен path-level audit Bucket A против `origin/main`:
    - `.gitignore`, `core/framework/runtime/README.md`, `docs/browser-extension-setup.html`,
      `docs/configuration.md`, `docs/developer-guide.md`, `docs/environment-setup.md` — synced;
    - `README.md` — only whitespace-level delta kept locally (no semantic divergence).
  - regression validation (April 11, 2026):
    - `./scripts/upstream_sync_preflight.sh` -> pass;
    - `./scripts/upstream_sync_regression_gate.sh` -> pass.
  - backlog status artifacts refreshed (`docs/ops/backlog-status/latest.json`).

## Execution Wave: MCP Health Findings Remediation

141. `P0` Fix Google/Files MCP Health Findings
- Status: `done`
- Scope:
  - устранить `google: HTTP 400` деградацию в health checks при протухшем `GOOGLE_ACCESS_TOKEN`;
  - устранить ложный `files_tools_runtime` fail при отсутствии свежих registration-событий в лог-окне.
- Done when:
  - `scripts/mcp_health_summary.py` возвращает `status: ok` в текущем runtime;
  - `scripts/verify_access_stack.sh` показывает Google `OK` path при доступном refresh flow.
- Progress:
  - `scripts/mcp_health_summary.py`:
    - добавлен Google refresh-fallback (`refresh_token` grant + tokeninfo re-check);
    - `files_tools_runtime` проверка переведена в activity-aware режим:
      - `failure_detected` -> fail,
      - `registered` -> ok,
      - `no_recent_activity` (без сигналов в логах) -> ok;
  - `scripts/verify_access_stack.sh`:
    - Google check обновлен:
      - access token path;
      - fallback refresh path без мутации `.env`.
  - Validation (April 11, 2026):
    - `uv run python scripts/mcp_health_summary.py --dotenv .env --since-minutes 20` -> `status: ok`, `ok: 5/5`;
    - `./scripts/verify_access_stack.sh` -> Google `OK` via `refresh-fallback`;
    - `./scripts/check_runtime_parity.sh` -> pass;
    - `uv run --active ruff check scripts/mcp_health_summary.py` -> `All checks passed`.

## Execution Wave: Google OAuth Token Lifecycle Hardening

142. `P0` Google OAuth Token Runtime Auto-Refresh Hardening
- Status: `done`
- Scope:
  - внедрить runtime-проверку протухшего Google access token и авто-refresh через refresh token;
  - обновлять рабочие runtime-артефакты токена без restart (`token file + expiry metadata`);
  - устранить permission edge-case между sidecar (root) и `hive-core` (`hiveuser`).
- Done when:
  - при истекшем токене runtime автоматически получает свежий токен и продолжает работу;
  - token lifecycle стабилен в контейнерном режиме.
- Progress:
  - реализован auto-refresh в `tools/src/aden_tools/tools/google_auth.py`;
  - добавлена запись expiry metadata (`google_access_token.meta.json`) в `scripts/google_token_refresher_daemon.py`;
  - исправлены ownership/permissions для `/data/storage/secrets/*` (совместимость root sidecar + hiveuser runtime);
  - обновлён `scripts/google_token_auto_refresh.sh` (token + meta sync);
  - добавлены тесты `tools/tests/tools/test_google_auth.py` (`4 passed`);
  - container validation: forced-expiry E2E path подтверждает refresh и обновление meta-файла.
  - Validation (April 11, 2026):
    - `docker compose up -d --build hive-core google-token-refresher` -> pass (`hive-core healthy`, refresher running);
    - `docker compose logs --tail=80 google-token-refresher` -> `refresh ok expires_in=3599`;
    - forced-expiry check inside container (`uv run python ... get_google_access_token_from_env_or_file()`) -> token refreshed, meta updated;
    - token/meta file ownership aligned to `hiveuser:hiveuser`.

143. `P1` Token Freshness Observability in MCP Health
- Status: `done`
- Scope:
  - расширить health summary метриками token freshness (`ttl_seconds`, `expires_at`, `source=file|env|refresh`);
  - добавить warning/critical пороги по времени до expiry.
- Done when:
  - `scripts/mcp_health_summary.py` показывает freshness-статус и прогноз риска деградации до фактической ошибки.
- Progress:
  - `scripts/mcp_health_summary.py` расширен freshness observability:
    - `token_source` (`file|env|refresh_fallback`);
    - `freshness` payload (`known`, `level`, `ttl_seconds`, `expires_at`, `thresholds`);
    - env thresholds: `HIVE_GOOGLE_TOKEN_WARN_TTL_SECONDS` (default `900`),
      `HIVE_GOOGLE_TOKEN_CRITICAL_TTL_SECONDS` (default `120`);
    - при `freshness.level=critical` Google check переводится в degraded even if tokeninfo still `HTTP 200`;
  - добавлены unit tests:
    - `scripts/tests/test_mcp_health_summary.py` (`5 passed`);
  - runbook updated:
    - `docs/LOCAL_PROD_RUNBOOK.md` (meta file + freshness thresholds).
- Validation (April 11, 2026):
  - `uv run --active ruff check scripts/mcp_health_summary.py scripts/tests/test_mcp_health_summary.py` -> `All checks passed`;
  - `uv run --active pytest scripts/tests/test_mcp_health_summary.py -q` -> `5 passed`;
  - `uv run python scripts/mcp_health_summary.py --dotenv .env --since-minutes 20 --json` ->
    Google detail includes `token_source` + `freshness` block, summary `status: ok`.

144. `P1` Consecutive Refresh Failure Alerting (Ops + Telegram)
- Status: `done`
- Scope:
  - фиксировать счётчик подряд идущих refresh failures в sidecar state;
  - отправлять proactive alert в Telegram после порога отказов.
- Done when:
  - оператор получает явный alert до деградации Google MCP в runtime.
- Progress:
  - `scripts/google_token_refresher_daemon.py` расширен alerting-контуром:
    - persistent state: `/data/storage/secrets/google_refresh_state.json`;
    - counters: `consecutive_failures`, `total_failures`, `total_success`, `last_success_at`, `last_failure_at`, `last_alert_at`;
    - Telegram alert при пороге с cooldown:
      - `GOOGLE_REFRESH_ALERT_ENABLED` (default `1`);
      - `GOOGLE_REFRESH_ALERT_FAILURE_THRESHOLD` (default `3`);
      - `GOOGLE_REFRESH_ALERT_COOLDOWN_SECONDS` (default `3600`);
      - `GOOGLE_REFRESH_ALERT_CHAT_IDS` (comma-separated).
  - добавлены unit tests:
    - `scripts/tests/test_google_token_refresher_daemon.py` (`6 passed`);
  - `docker-compose.yml` обновлен env wiring для refresher state/alert vars;
  - `scripts/verify_access_stack.sh` дополнен проверкой refresher state health (`consecutive_failures < threshold`);
  - runtime validation:
    - sidecar стартует с новым логом `state=... alert_enabled=1 threshold=3`;
    - state-file создается и обновляется (`consecutive_failures=0`, `total_success>=1`).
  - added operator helper:
    - `scripts/telegram_chat_id_probe.py` (+ tests) для быстрого discovery chat IDs и optional upsert в `.env`.
  - live drill closure:
    - найден runtime chat id из bridge logs: `188207447`;
    - `.env` обновлен: `GOOGLE_REFRESH_ALERT_CHAT_IDS=188207447`;
    - выполнен alert drill через refresher alert path (`_send_failure_alert_if_needed`) в контейнере `google-token-refresher`;
    - result: `{'sent': True, 'detail': 'sent'}`.

145. `P1` Google OAuth Rotation and Re-Auth Runbook
- Status: `done`
- Scope:
  - оформить SOP по rotation client secret/refresh token и аварийной re-auth;
  - добавить пошаговый drill и rollback-процедуру.
- Done when:
  - re-auth/rotation выполняется детерминированно по runbook без даунтайма сервиса.
- Progress:
  - добавлен runbook:
    - `docs/ops/google-oauth-rotation-runbook.md`;
  - покрыты сценарии:
    - client secret rotation (same client id),
    - refresh token rotation / full re-auth,
    - client id migration,
    - rollback procedure + post-rotation checks;
  - `docs/LOCAL_PROD_RUNBOOK.md` синхронизирован ссылкой на новый SOP.

146. `P1` Scheduled Google MCP Canary Smoke
- Status: `done`
- Scope:
  - добавить cron/launchd job для периодического canary smoke (`google docs/sheets/gmail` read-only probes);
  - сохранять артефакт последнего smoke-результата в ops-статус.
- Done when:
  - есть регулярный canary контур, который ловит регрессии токена и scope до ручных инцидентов.
- Progress:
  - добавлен canary artifact generator:
    - `scripts/google_mcp_canary.py` (persist `latest.json` + timestamped artifact + `latest.md`);
  - добавлены unit tests:
    - `scripts/tests/test_google_mcp_canary.py` (`2 passed`);
  - добавлены installers:
    - cron: `install/status/uninstall_google_canary_cron.sh`;
    - launchd: `install/status/uninstall_google_canary_launchd.sh`;
  - runbook/env sync:
    - `.env.mcp.example` (canary env vars),
    - `docs/LOCAL_PROD_RUNBOOK.md` (manual run + schedule install commands);
 - Validation (April 11, 2026):
    - `uv run python scripts/google_mcp_canary.py --dotenv .env --artifact-dir docs/ops/google-canary` -> pass;
    - artifacts updated:
      - `docs/ops/google-canary/latest.json`
      - `docs/ops/google-canary/latest.md`.

147. `P1` Container-Only Telegram Test Chat Baseline
- Status: `done`
- Scope:
  - зафиксировать единый test chat id для контейнерных smoke/alert сценариев;
  - убрать зависимость от host-only запуска probe/канареек в инструкциях.
- Done when:
  - refresher alerts имеют стабильный fallback chat id в docker runtime;
  - probe-скрипт обновляет и alert ids, и test id;
  - runbook отражает container-only путь.
- Progress:
  - добавлен unified fallback env:
    - `HIVE_TELEGRAM_TEST_CHAT_ID` в `docker-compose.yml` (`hive-core`, `google-token-refresher`);
    - `.env.mcp.example` + `.env` синхронизированы.
  - `scripts/google_token_refresher_daemon.py`:
    - добавлен `_resolve_alert_chat_ids_raw()` с fallback order:
      `GOOGLE_REFRESH_ALERT_CHAT_IDS` -> `GOOGLE_REFRESH_ALERT_CHAT_ID` -> `HIVE_TELEGRAM_TEST_CHAT_ID`.
  - `scripts/telegram_chat_id_probe.py`:
    - `--write-alert-env` теперь пишет:
      - `GOOGLE_REFRESH_ALERT_CHAT_IDS`,
      - `HIVE_TELEGRAM_TEST_CHAT_ID` (first discovered id).
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md`,
    - `docs/ops/google-oauth-rotation-runbook.md` (container-exec commands).
  - Validation (April 11, 2026):
    - container tests: `docker compose exec -T hive-core uv run pytest scripts/tests/test_google_token_refresher_daemon.py scripts/tests/test_telegram_chat_id_probe.py -q` -> `10 passed`;
    - runtime env check:
      - `docker compose exec -T hive-core ...` -> `HIVE_TELEGRAM_TEST_CHAT_ID=188207447`,
    - `docker compose exec -T google-token-refresher ...` -> `HIVE_TELEGRAM_TEST_CHAT_ID=188207447`;
    - refresher logs: `refresh ok expires_in=3599`.

148. `P1` Container Runtime Docs Parity for Ops/Backlog Scripts
- Status: `done`
- Scope:
  - убрать рассинхрон, когда `hive-core` не может запускать backlog/ops scripts из-за отсутствия docs в image;
  - обеспечить container-only выполнение `validate_backlog_markdown.py` и `backlog_status.py`.
- Done when:
  - внутри `hive-core` доступны необходимые docs paths;
  - backlog checks проходят без bind-mount workaround.
- Progress:
  - `.dockerignore` переведен на allow-list runtime docs:
    - `docs/autonomous-factory/**`,
    - `docs/ops/**`,
    - `docs/LOCAL_PROD_RUNBOOK.md`,
    - `docs/browser-extension-setup.html`,
    - `docs/configuration.md`,
    - `docs/developer-guide.md`,
    - `docs/environment-setup.md`;
  - `Dockerfile` обновлен:
    - `COPY docs/ docs/`;
    - ownership fix: `/app/docs` -> `hiveuser:hiveuser` (write access для ops artifacts).
  - Validation (April 11, 2026):
    - `docker compose up -d --build hive-core` -> pass;
    - `docker compose exec -T hive-core uv run python scripts/validate_backlog_markdown.py` -> pass;
    - `docker compose exec -T hive-core uv run python scripts/backlog_status.py --json` ->
      `tasks_total=148`, `done=148`, `todo=0`;
    - `docker compose exec -T hive-core uv run python scripts/backlog_status_artifact.py` -> pass;
    - `docker compose exec -T hive-core uv run python scripts/backlog_status_hygiene.py --keep 50` -> pass.

## Execution Wave: Upstream Continuation (Wave 3, bounded scope)

149. `P1` Container Ops Toolchain Baseline (`git` + `jq`)
- Status: `done`
- Scope:
  - обеспечить выполнение upstream/preflight workflows в docker runtime без host tool dependencies;
  - добавить `git` и `jq` в `hive-core` image.
- Done when:
  - `git`/`jq` доступны внутри `hive-core`.
- Progress:
  - `Dockerfile` обновлён:
    - apt install: `git`, `jq`, `ca-certificates`;
  - Validation (April 11, 2026):
    - `docker compose up -d --build hive-core` -> pass;
    - `docker compose exec -T hive-core sh -lc 'git --version && jq --version'` ->
      `git version 2.47.3`, `jq-1.7`.
    - `docker compose up -d --force-recreate google-token-refresher hive-scheduler` ->
      all runtime services on `hive-hive-core` image.

150. `P0` Upstream Delta Refresh Snapshot (Wave 3 kickoff)
- Status: `done`
- Scope:
  - зафиксировать актуальный upstream delta snapshot из контейнерного выполнения;
  - использовать snapshot как fixed input для следующего merge wave.
- Done when:
  - есть подтверждённые counts по bucket A/B/C + unclassified.
- Progress:
  - Container run (bind-mount workspace):
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core sh -lc 'git fetch origin main --quiet && uv run --no-project python scripts/upstream_delta_status.py --base-ref HEAD --target-ref origin/main --json'`;
  - Snapshot result:
    - total entries: `36`;
    - bucket A: `7`;
    - bucket B: `11`;
    - bucket C: `2`;
    - unclassified: `16`.

151. `P1` Controlled Merge Batch A (Wave 3 low-risk docs/meta)
- Status: `done`
- Scope:
  - безопасно интегрировать bucket A low-risk paths из `origin/main` без регрессий локального UX.
- Done when:
  - bucket A paths синхронизированы;
  - docs navigation/sync checks pass.
- Progress:
  - synchronized to `origin/main`:
    - `.gitignore`
    - `README.md`
    - `core/framework/runtime/README.md`
    - `docs/browser-extension-setup.html`
    - `docs/configuration.md`
    - `docs/developer-guide.md`
    - `docs/environment-setup.md`;
  - validation:
    - `git diff --name-only origin/main -- <bucket-a-paths>` -> empty;
    - `uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> pass;
    - `uv run --no-project python scripts/check_runbook_sync.py` -> pass;
    - `uv run --no-project python scripts/check_upstream_bucket_contract_sync.py` -> pass.

152. `P1` Unclassified Delta Governance Closure (Wave 3)
- Status: `done`
- Scope:
  - классифицировать 16 unclassified paths (merge/defer/drop decisions);
  - обновить decision registry/report для детерминированного preflight.
- Done when:
  - unclassified coverage complete;
  - governance checks pass.
- Progress:
  - `uv run --no-project python scripts/check_unclassified_delta_decisions.py` -> pass:
    - `covered_unclassified=16`
    - `stale_decisions=0`
    - `decision_tally=already-absorbed:16`;
  - `uv run --no-project python scripts/render_unclassified_decision_report.py --check docs/ops/upstream-unclassified-decisions.md` -> pass.

153. `P0` Regression Gate After Wave 3 Integration
- Status: `done`
- Scope:
  - прогнать full regression gate после задач 151/152;
  - обновить backlog status artifacts + ops summary.
- Done when:
  - gate green;
  - status artifacts синхронизированы.
- Progress:
  - regression tests (container):
    - `docker compose exec -T hive-core uv run pytest scripts/tests/test_upstream_delta_status.py scripts/tests/test_check_upstream_bucket_contract_sync.py scripts/tests/test_check_unclassified_delta_decisions.py scripts/tests/test_render_unclassified_decision_report.py scripts/tests/test_check_acceptance_docs_navigation.py scripts/tests/test_check_runbook_sync.py scripts/tests/test_check_acceptance_runbook_sanity_sync.py scripts/tests/test_backlog_status.py scripts/tests/test_backlog_status_artifact.py scripts/tests/test_backlog_status_hygiene.py -q`
      -> `27 passed`;
  - regression checks (container-run, bind mount):
    - `uv run --no-project python scripts/validate_backlog_markdown.py` -> pass;
    - `uv run --no-project python scripts/backlog_status.py --json` -> pass;
    - `uv run --no-project python scripts/check_upstream_bucket_contract_sync.py` -> pass;
    - `uv run --no-project python scripts/check_unclassified_delta_decisions.py` -> pass;
    - `uv run --no-project python scripts/render_unclassified_decision_report.py --check ...` -> pass;
  - status artifacts:
    - `uv run --no-project python scripts/backlog_status_artifact.py` -> pass;
    - `uv run --no-project python scripts/backlog_status_hygiene.py --keep 50` -> pass.

## Execution Wave: Upstream Continuation (Wave 4, memory runtime)

154. `P1` Controlled Merge Batch B (Wave 4 medium-risk runtime/memory-v2)
- Status: `done`
- Scope:
  - синхронизировать bucket B paths из `origin/main`:
    - `core/framework/agents/queen/nodes/__init__.py`
    - `core/framework/agents/queen/queen_memory_v2.py`
    - `core/framework/agents/queen/recall_selector.py`
    - `core/framework/graph/context.py`
    - `core/framework/graph/executor.py`
    - `core/framework/graph/worker_agent.py`
    - `core/framework/runtime/agent_runtime.py`
    - `core/framework/runtime/execution_stream.py`
    - `core/framework/tools/queen_lifecycle_tools.py`
    - `core/tests/test_event_bus.py`
    - `core/tests/test_queen_memory.py`
- Done when:
  - bucket B paths совпадают с upstream;
  - профильные runtime/memory tests green.
- Progress:
  - bucket B synced from `origin/main` in container workflow:
    - `core/framework/agents/queen/nodes/__init__.py`
    - `core/framework/agents/queen/queen_memory_v2.py`
    - `core/framework/agents/queen/recall_selector.py`
    - `core/framework/graph/context.py`
    - `core/framework/graph/executor.py`
    - `core/framework/graph/worker_agent.py`
    - `core/framework/runtime/agent_runtime.py`
    - `core/framework/runtime/execution_stream.py`
    - `core/framework/tools/queen_lifecycle_tools.py`
    - `core/tests/test_event_bus.py` (source synced; file is new relative to local base branch)
    - `core/tests/test_queen_memory.py`;
  - compatibility patch for local hybrid path:
    - `core/framework/agents/queen/reflection_agent.py` updated to work with refreshed
      `queen_memory_v2` API (global-memory constants/helpers + stricter type validation);
  - Validation (April 11, 2026):
    - `docker run --rm -e UV_PROJECT_ENVIRONMENT=/tmp/uvproj -v "$PWD":/workspace -w /workspace hive-hive-core uv run pytest core/tests/test_event_bus.py core/tests/test_queen_memory.py core/tests/test_session_manager_worker_handoff.py -q` -> `83 passed`.

155. `P1` Memory Architecture Transition Decision (Wave 4, bucket C)
- Status: `done`
- Scope:
  - принять контролируемое решение для bucket C:
    - `core/framework/agents/queen/queen_memory.py` (upstream delete)
    - `core/framework/tools/queen_memory_tools.py` (upstream delete);
  - зафиксировать: merge/delete now или explicit defer с compatibility justification.
- Done when:
  - decision registry отражает принятое решение;
  - preflight decision checks pass.
- Progress:
  - decision reaffirmed: **defer destructive bucket C removals** (keep hybrid compatibility path);
  - updated decision record:
    - `docs/autonomous-factory/17-memory-architecture-transition-decision.md`
      (`Wave 4 Revalidation (April 11, 2026)` section);
  - governance validation:
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/check_unclassified_delta_decisions.py` -> pass;
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/render_unclassified_decision_report.py --check docs/ops/upstream-unclassified-decisions.md` -> pass.

156. `P0` Regression Gate After Wave 4 Integration
- Status: `done`
- Scope:
  - прогнать regression gate после 154/155;
  - обновить backlog status artifacts.
- Done when:
  - regression green;
  - `docs/ops/backlog-status/latest.json` синхронизирован.
- Progress:
  - regression checks (container):
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/validate_backlog_markdown.py` -> pass;
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/backlog_status.py --json` -> pass;
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/check_upstream_bucket_contract_sync.py` -> pass;
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> pass;
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/check_runbook_sync.py` -> pass;
  - status artifacts synced (container run + bind mount):
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/backlog_status_artifact.py` -> pass;
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/backlog_status_hygiene.py --keep 50 --yes` -> pass.

## Execution Wave: Container Ops Runner (Wave 5)

157. `P1` Add `hive-ops` Compose Runner for Container-Only Workspace Commands
- Status: `done`
- Scope:
  - добавить dedicated compose service для one-shot ops/test commands поверх bind-mounted workspace;
  - обеспечить persistent uv caches для быстрых повторных прогонов.
- Done when:
  - `docker compose --profile ops run --rm hive-ops ...` выполняет `uv run` команды в workspace без heavy cold-start на каждый запуск.
- Progress:
  - `docker-compose.yml`:
    - добавлен service `hive-ops` (profile: `ops`);
    - bind mounts:
      - `./:/workspace`
      - `./.cache/uv:/home/hiveuser/.cache/uv`
      - `./.cache/uvproj:/data/uvproj`;
    - env: `UV_PROJECT_ENVIRONMENT=/data/uvproj`, `PYTHONPATH=/workspace/tools/src`.
  - Validation (April 11, 2026):
    - `docker compose --profile ops run --rm --no-deps hive-ops uv run --no-project python scripts/backlog_status.py --json` -> pass.

158. `P1` Add Operator Wrapper Script for `hive-ops` Runner
- Status: `done`
- Scope:
  - создать удобный wrapper для container-only запуска ops/test команд;
  - поддержать optional image build и profile wiring.
- Done when:
  - один стабильный entrypoint для ops checks: `./scripts/hive_ops_run.sh <command...>`.
- Progress:
  - добавлен script:
    - `scripts/hive_ops_run.sh`;
  - возможности:
    - usage/help;
    - optional `--build`;
    - auto-build when `hive-hive-core` image missing;
    - auto-create cache dirs `.cache/uv` and `.cache/uvproj`;
    - run path: `docker compose --profile ops run --rm --no-deps hive-ops ...`.
  - Validation:
    - `bash -n scripts/hive_ops_run.sh` -> pass;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status.py --json` -> pass;
    - repeated run latency check:
      - `time ./scripts/hive_ops_run.sh uv run --no-project python scripts/validate_backlog_markdown.py` -> ~`0.35s`.

159. `P0` Runbook Sync + Regression Gate for Container Ops Runner
- Status: `done`
- Scope:
  - закрепить runner в локальном runbook;
  - прогнать regression checks и backlog artifact sync через container workflow.
- Done when:
  - runbook содержит `hive_ops_run.sh` workflow;
  - backlog checks + sync checks green.
- Progress:
  - runbook updated:
    - `docs/LOCAL_PROD_RUNBOOK.md`:
      - добавлен section `Container-only ops runner`;
      - `export_mcp_inventory` переведен на `hive_ops_run.sh`.
  - regression checks:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/validate_backlog_markdown.py` -> pass;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status.py --json` -> pass;
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/check_upstream_bucket_contract_sync.py` -> pass;
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> pass;
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/check_runbook_sync.py` -> pass;
 - backlog artifacts:
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/backlog_status_artifact.py` -> pass;
    - `docker run --rm -v "$PWD":/workspace -w /workspace hive-hive-core uv run --no-project python scripts/backlog_status_hygiene.py --keep 50 --yes` -> pass.

## Execution Wave: Container Preflight Hardening (Wave 6)

160. `P1` Make Runtime Parity Check Resilient Without `curl`
- Status: `done`
- Scope:
  - убрать hard-fail на отсутствии `curl` в `scripts/check_runtime_parity.sh`;
  - сохранить текущий JSON contract validation path.
- Done when:
  - runtime parity проходит в `hive-ops` контейнере даже без установленного `curl`.
- Progress:
  - `scripts/check_runtime_parity.sh` обновлен:
    - `curl` переведен в optional dependency;
    - добавлен fallback HTTP transport через `uv run --no-project python` + `urllib` для GET/POST JSON.
  - `jq` validation path сохранен без изменений.
- Validation (April 11, 2026):
  - `./scripts/hive_ops_preflight.sh` -> pass (`Runtime parity` step green with warning fallback).

161. `P1` Sync Acceptance Automation Map With Container-First Ops Workflow
- Status: `done`
- Scope:
  - дополнить acceptance map container-first entrypoints и эквиваленты backlog status refresh;
  - не ломать existing guardrail markers.
- Done when:
  - `docs/ops/acceptance-automation-map.md` содержит `hive_ops_run.sh` / `hive_ops_preflight.sh` и container-first cadence.
- Progress:
  - обновлен `docs/ops/acceptance-automation-map.md`:
    - section `Container-First Entry Points`;
    - container-first backlog status auto-refresh sequence;
    - обновленные `Recommended Cadence` и `Quick Start` с preflight-first flow.
- Validation (April 11, 2026):
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> pass.

162. `P0` Re-Run Container Preflight + Backlog Artifact Sync After Hardening
- Status: `done`
- Scope:
  - прогнать full preflight после 160/161;
  - синхронизировать backlog status artifacts.
- Done when:
  - `hive_ops_preflight` green;
  - `docs/ops/backlog-status/latest.json` отражает обновленный backlog.
- Progress:
  - preflight (container-first):
    - `./scripts/hive_ops_preflight.sh` -> pass;
 - artifact refresh/hygiene выполнены внутри preflight:
    - `scripts/backlog_status_artifact.py` -> pass;
    - `scripts/backlog_status_hygiene.py --keep 50 --yes` -> pass.

## Execution Wave: Docker Build Latency Hardening (Wave 7)

163. `P1` Reorder Playwright Browser Install Layer to Preserve Cache Across Code Edits
- Status: `done`
- Scope:
  - уменьшить rebuild latency для `hive-core` при code-only изменениях;
  - не убирать Playwright runtime capability.
- Done when:
  - browser install step расположен до `COPY core/framework` / `COPY tools/src`, чтобы не инвалидироваться при каждом изменении исходников.
- Progress:
  - `Dockerfile` обновлен:
    - шаг `ARG HIVE_DOCKER_INSTALL_PLAYWRIGHT` + `uv run playwright install --with-deps chromium`
      перенесен сразу после `uv sync --frozen --no-install-workspace`;
    - добавлен комментарий про cache-friendly ordering.
- Validation (April 11, 2026):
  - `docker compose build --build-arg HIVE_DOCKER_INSTALL_PLAYWRIGHT=0 hive-core` -> pass (fast build path).

164. `P0` Re-Validate Container Ops Preflight After Dockerfile Build-Latency Refactor
- Status: `done`
- Scope:
  - убедиться, что после 163 весь container-only preflight по-прежнему green;
  - синхронизировать backlog status artifacts.
- Done when:
  - `./scripts/hive_ops_preflight.sh` завершается успешно;
  - `docs/ops/backlog-status/latest.json` обновлён.
- Progress:
 - full preflight re-run completed:
    - `./scripts/hive_ops_preflight.sh` -> pass;
  - backlog artifact refresh/hygiene внутри preflight -> pass.

## Execution Wave: Container-First Runbook Completion + Build Baseline (Wave 8)

165. `P1` Convert Remaining Runbook `uv run` Commands to Container-First `hive_ops_run`
- Status: `done`
- Scope:
  - перевести оставшиеся host-style `uv run python scripts/...` команды в
    `docs/LOCAL_PROD_RUNBOOK.md` на container-first pattern:
    `./scripts/hive_ops_run.sh uv run --no-project python ...`.
- Done when:
  - в runbook не осталось прямых host-style `uv run python scripts/...` команд;
  - команды Google/Audit/Acceptance/MCP health используют единый container ops runner.
- Progress:
  - обновлены секции:
    - Google OAuth/smoke/canary/probe;
    - Credential audit;
    - Acceptance weekly digest + sanity checks;
    - Backlog status sanity sequence;
    - MCP health summary.
- Validation (April 11, 2026):
  - `rg -n "(^|\\s)uv run python scripts/" docs/LOCAL_PROD_RUNBOOK.md` -> no matches.

166. `P1` Sync Runbook Sanity Guardrail With Container-First Command Markers
- Status: `done`
- Scope:
  - обновить `scripts/check_acceptance_runbook_sanity_sync.py` на новый command-set маркеров
    (`hive_ops_run` вместо direct `uv run`).
- Done when:
  - sanity checker green на обновленном runbook.
- Progress:
  - `scripts/check_acceptance_runbook_sanity_sync.py`:
    - `REQUIRED_COMMAND_MARKERS` переведены на
      `./scripts/hive_ops_run.sh uv run --no-project python ...`.
- Validation (April 11, 2026):
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> pass;
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_runbook_sync.py` -> pass;
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> pass.

167. `P0` Capture Full `hive-core` Image Build Baseline After Dockerfile Layer Reorder
- Status: `done`
- Scope:
  - выполнить отдельный full build с `HIVE_DOCKER_INSTALL_PLAYWRIGHT=1`;
  - зафиксировать baseline времени (cold + warm cache).
- Done when:
  - cold full build time captured;
  - immediate warm rebuild time captured.
- Progress:
  - cold full build:
    - `/usr/bin/time -p docker compose build --build-arg HIVE_DOCKER_INSTALL_PLAYWRIGHT=1 hive-core`
      -> `real 3830.78`, `user 2.68`, `sys 2.38`;
 - warm full rebuild:
    - `/usr/bin/time -p docker compose build --build-arg HIVE_DOCKER_INSTALL_PLAYWRIGHT=1 hive-core`
      -> `real 2.95`, `user 0.18`, `sys 0.23`.

## Execution Wave: Toolchain Approval Hardening (Wave 9)

168. `P0` Stronger User-Approval Contract for Toolchain Apply
- Status: `done`
- Scope:
  - усилить подтверждение применения toolchain profile (plan fingerprint + token);
  - сделать двухфазный flow `plan -> explicit approve -> apply` устойчивым к accidental apply;
  - сохранить текущий safety contract (`dry-run` by default).
- Done when:
  - confirm token включает fingerprint конкретного плана;
  - apply отклоняется при token mismatch;
  - покрыто unit-тестами detector/apply flow.
- Progress:
  - `scripts/detect_project_toolchains.py` усилен:
    - добавлен `plan_fingerprint` (stable hash от content-плана без привязки к temp clone path);
    - `confirm_token` теперь формата `APPLY_<TOOLCHAINS>_<FINGERPRINT>` (пример: `APPLY_NODE_6AA83D6E`);
    - `--format env` дополнен `HIVE_TOOLCHAIN_PLAN_FINGERPRINT=...`.
  - обновлены unit-тесты detector:
    - проверки token/fingerprint формата;
    - добавлен test на смену fingerprint при изменении marker set.
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest scripts/tests/test_detect_project_toolchains.py -q` -> `5 passed`;
  - smoke:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/detect_project_toolchains.py --workspace . --format human`
      -> `plan_fingerprint` и `confirm_token` присутствуют.

169. `P1` Container-First Toolchain Commands in Runbook
- Status: `done`
- Scope:
  - перевести разделы toolchain planning/apply на container-first pattern;
  - убрать host-only команды там, где должен использоваться `hive_ops_run`.
- Done when:
  - runbook содержит единый container-first operator flow для toolchain профилей.
- Progress:
  - `scripts/apply_hive_toolchain_profile.sh` переведен на container-first detect path:
    - вне контейнера detector вызывается через `./scripts/hive_ops_run.sh uv run --no-project python ...`;
    - в контейнере используется direct `uv run` fallback (`/.dockerenv`);
    - usage/examples обновлены на fingerprint token формат.
  - `docs/LOCAL_PROD_RUNBOOK.md` обновлен:
    - toolchain planning команды переведены на `hive_ops_run.sh`;
    - примеры `--confirm` токена обновлены (`APPLY_NODE_<FINGERPRINT>`).
- Validation (April 12, 2026):
  - `bash scripts/apply_hive_toolchain_profile.sh --workspace .` -> dry-run success, printed token `APPLY_NODE_<FINGERPRINT>`;
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_runbook_sync.py` -> pass;
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> pass.

170. `P0` Regression + Backlog Artifact Sync After Toolchain Hardening
- Status: `done`
- Scope:
  - прогнать targeted tests + backlog validators после 168/169;
  - обновить backlog status artifacts/index.
- Done when:
  - regression green;
  - `docs/ops/backlog-status/latest.json` синхронизирован.
- Progress:
  - regression checks:
    - `bash -n scripts/apply_hive_toolchain_profile.sh` -> pass;
    - `./scripts/hive_ops_run.sh uv run pytest scripts/tests/test_detect_project_toolchains.py scripts/tests/test_check_runbook_sync.py scripts/tests/test_check_acceptance_runbook_sanity_sync.py -q`
      -> `10 passed`;
  - backlog artifact refresh:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_artifact.py` -> pass;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status_hygiene.py --keep 50 --yes` -> pass.
- Validation (April 12, 2026 follow-up):
  - full runtime gate:
    - `./scripts/autonomous_acceptance_gate.sh` -> `ok=13 failed=0`;
  - backlog/status sync:
    - `./scripts/hive_ops_run.sh uv run python scripts/validate_backlog_markdown.py`
      -> `[ok] backlog validation passed`, `tasks_total=173`, `in_progress=[]`, `focus_refs=[]`.

171. `P0` Project-Level Toolchain Plan/Approve API Flow
- Status: `done`
- Scope:
  - добавить project-aware API endpoints для двухфазного flow:
    `plan -> approve` с обязательным confirm token;
  - хранить pending/approved toolchain profile в project metadata;
  - добавить revalidation на approve (план не должен измениться между шагами).
- Done when:
  - API поддерживает явный approval contract для toolchain профиля;
  - token mismatch и plan drift обрабатываются безопасно (`409` + actionable payload).
- Progress:
  - добавлен `core/framework/server/project_toolchain.py`:
    - source resolution (`workspace_path | repository`);
    - runtime detect plan (через `scripts/detect_project_toolchains.py`);
    - apply command/env export generation;
  - в project metadata добавлен `toolchain_profile` (`project_store` + `session_manager`);
  - добавлены endpoints:
    - `GET /api/projects/{id}/toolchain-profile`
    - `POST /api/projects/{id}/toolchain-profile/plan`
    - `POST /api/projects/{id}/toolchain-profile/approve`;
  - approve flow:
    - mandatory `confirm_token`;
    - optional `revalidate` (default `true`);
    - plan drift -> `409` + refreshed `pending_plan`.
  - добавлены API tests:
    - `test_project_toolchain_profile_plan_and_approve`
    - `test_project_toolchain_profile_approve_revalidate_detects_plan_drift`.
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "toolchain_profile or project_onboarding" -q`
    -> `6 passed`.
  - live API smoke (docker runtime):
    - `POST /api/projects/default/toolchain-profile/plan` (`workspace_path=/app`) -> `200` (`confirm_token` includes fingerprint);
    - `POST /api/projects/default/toolchain-profile/approve` with token -> `200`;
    - `GET /api/projects/default/toolchain-profile` -> `approved_plan` present, `pending_plan=null`.

172. `P1` Workspace UI Toolchain Control Center
- Status: `done`
- Scope:
  - добавить в workspace UI доступный control center для toolchain flow:
    `plan -> review token -> approve`;
  - отобразить instructions (`preview/apply command`, `env exports`) для оператора.
- Done when:
  - оператор может пройти двухфазный toolchain flow из web UI без ручного API вызова;
  - UI показывает pending fingerprint/stack/toolchains и актуальный confirm token.
- Progress:
  - frontend API расширен:
    - `projectsApi.toolchainProfile(...)`
    - `projectsApi.planToolchainProfile(...)`
    - `projectsApi.approveToolchainProfile(...)`;
  - типы `ProjectInfo` расширены полем `toolchain_profile`;
  - в `workspace` добавлен `Toolchain` modal:
    - source inputs (`workspace path` / `repository`);
    - `Plan` и `Approve` actions;
    - pending summary (fingerprint/stack/toolchains);
    - operator instructions (`preview/apply`, `env exports`).
- Validation (April 12, 2026):
  - frontend build (containerized):
    - `docker run --rm -v "$PWD":/work -w /work/core/frontend node:22-bookworm bash -lc 'npm ci --no-audit --no-fund >/tmp/npm-ci.log && npm run build'`
      -> success;
  - runtime deploy smoke:
    - refreshed `core/frontend/dist` in `hive-core` + restart -> `health=healthy`;
    - `Toolchain` control appears in top toolbar (workspace project controls).
  - detector tests:
    - `./scripts/hive_ops_run.sh uv run pytest scripts/tests/test_detect_project_toolchains.py -q`
      -> `5 passed`.

173. `P0` Telegram Bridge Toolchain Flow (Plan + Approve + Inline Confirm)
- Status: `done`
- Scope:
  - добавить Telegram команды:
    - `/toolchain` (status),
    - `/toolchain_plan [workspace|repo-url]`,
    - `/toolchain_approve [token]`;
  - добавить inline callbacks для `Plan` и `Approve Pending`;
  - связать bridge с project toolchain API (`plan/status/approve`).
- Done when:
  - toolchain flow доступен из Telegram без ручных HTTP вызовов;
  - approve возможен одной inline-кнопкой из результата plan.
- Progress:
  - `core/framework/server/telegram_bridge.py`:
    - добавлены команды в `setMyCommands`;
    - добавлена кнопка `Toolchain` в keyboard/inline status panel;
    - реализованы core API helpers + handlers:
      - `_send_toolchain_status`
      - `_plan_project_toolchain`
      - `_approve_project_toolchain`;
    - добавлены callback actions:
      - `show_toolchain`, `plan_toolchain`, `approve_toolchain`.
  - добавлены unit tests:
    - `/toolchain_plan` command dispatch;
    - `/toolchain_approve` command dispatch (with/without token);
    - inline callback dispatch for plan/approve.
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_telegram_bridge.py -q`
    -> `12 passed`;
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "toolchain_profile" -q`
    -> `2 passed`;
  - runtime hot-deploy:
    - synced bridge file into `hive-core`, restarted container, `health=healthy`;
    - logs confirm `Telegram bridge commands registered (22)` and bridge running.
- Validation (April 12, 2026 follow-up):
  - full rebuild/restart:
    - `docker compose up -d --build` -> all services `healthy`;
  - live runtime checks:
    - `GET /api/telegram/bridge/status` -> `status=ok`, `poller_owner=true`, `running=true`;
    - `/toolchain_plan` + `/toolchain_approve` flow confirmed with approved plan persisted in
      `GET /api/projects/default` (`toolchain_profile.approved_plan` present).

## Execution Wave: Runtime Signal Hardening (post-wave)

174. `P1` Telegram Polling Error Signal Quality
- Status: `done`
- Scope:
  - устранить пустые `Telegram bridge polling error:` сообщения в runtime логах;
  - сделать `last_poll_error` диагностически полезным даже для исключений без message.
- Done when:
  - в логах всегда есть тип ошибки (`TimeoutError`, `RuntimeError`, ...);
  - `/api/telegram/bridge/status` отдает непустой `last_poll_error` при fault-сценариях.
- Progress:
  - `core/framework/server/telegram_bridge.py`:
    - добавлен helper `_format_exception_details(exc)` для нормализации ошибок;
    - poll-loop теперь пишет `ClassName: message` или `ClassName` (если message empty) в
      `last_poll_error` и warning log.
  - `core/framework/server/tests/test_telegram_bridge.py`:
    - добавлены unit tests на форматирование ошибок:
      - empty-message exception -> type-only detail;
      - exception with message -> `Type: message`.
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_telegram_bridge.py -q`
    -> `14 passed`;
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "health or telegram_bridge_status_endpoint" -q`
    -> `2 passed`;
  - `docker compose up -d --build hive-core hive-scheduler` -> rebuilt + healthy.

## Execution Wave: Repo Provisioning + Telegram-First Factory (planned)

175. `P0` GitHub Repository Provisioning API (Native)
- Status: `done`
- Scope:
  - добавить server-side endpoint для создания GitHub repository из project context:
    `POST /api/projects/{id}/repository/provision`;
  - поддержать параметры `name`, `visibility`, `owner(org/user)`, `description`, `initialize_readme`;
  - после успешного create автоматически сохранить `repository` в metadata проекта.
- Done when:
  - репозиторий можно создать через API без ручного захода в GitHub UI;
  - проект автоматически привязывается к созданному repo URL/slug.
- Progress:
  - добавлен endpoint `POST /api/projects/{id}/repository/provision`;
  - реализован безопасный token resolution (credential store `github` -> env fallback);
  - реализовано создание repo через GitHub API (`/user/repos` или `/orgs/{owner}/repos`);
  - добавлен auto-bind: после create поле `project.repository` обновляется до `html_url`;
  - добавлен mapping ошибок GitHub API в operator-friendly HTTP ответы (`401/403/404/409/502`).
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "repository_provision or projects_crud_flow" -q`
    -> `4 passed`.

176. `P0` Telegram `/newrepo` Command + Safe Confirm Flow
- Status: `done`
- Scope:
  - добавить команду `/newrepo` в Telegram bridge (arguments + inline confirm);
  - двухфазный apply-контракт: `plan -> confirm -> create` (без accidental create);
  - после create автоматически предложить `/onboard`.
- Done when:
  - оператор создаёт репозиторий из Telegram одной процедурой;
  - повторный клик/дубликат callback не создаёт репозиторий повторно.
- Progress:
  - добавлена команда `/newrepo` в bridge command router;
  - реализован двухфазный flow `plan -> confirm` с pending-state на чат;
  - confirm выполняет server API `POST /api/projects/{id}/repository/provision`;
  - callback подтверждение стало явным (`✅ Selected: create repository`) + single-use behavior через callback consume/markup clear.
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_telegram_bridge.py core/framework/server/tests/test_api.py -k "newrepo or repository_provision" -q`
    -> `5 passed`.

177. `P0` Telegram `/repo` Bind Existing Repository
- Status: `done`
- Scope:
  - добавить команду `/repo <url|owner/repo>` для привязки существующего репозитория к active project;
  - валидация формата и доступности через GitHub API;
  - обновление project metadata (`repository`, optional `workspace_path` hint).
- Done when:
  - оператор может переключать проект на существующий репозиторий полностью из Telegram;
  - invalid/missing-access repo возвращает явную ошибку с remediation hint.
- Progress:
  - добавлен project API endpoint `POST /api/projects/{id}/repository/bind`;
  - bind flow валидирует формат `owner/repo|GitHub URL`, проверяет доступность repo через GitHub API и обновляет `project.repository`;
  - добавлена Telegram команда `/repo <url|owner/repo>`, связанная с bind endpoint.
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "repository_bind" -q`
    -> `2 passed`;
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_telegram_bridge.py -k "repo_command" -q`
    -> `1 passed`.

178. `P0` Telegram `/onboard` Command for Project Bootstrap
- Status: `done`
- Scope:
  - добавить Telegram команду `/onboard` с optional args (`stack`, `template_id`, `workspace_path`);
  - вызывать существующий onboarding API (`/api/projects/{id}/onboarding`) и отправлять compact report в чат;
  - показать next actions: `/toolchain_plan`, `/run`, checks policy.
- Done when:
  - оператор выполняет onboarding active project без перехода в Web UI;
  - отчет onboarding стабильно отображает `checks`, `manifest`, `dry_run`.
- Progress:
  - добавлена Telegram команда `/onboard` с optional args:
    `stack`, `template_id`, `workspace_path`, `repository`, `dry_run_command`;
  - bridge вызывает existing API `POST /api/projects/{id}/onboarding`;
  - добавлен compact onboarding report в чат:
    `ready`, `workspace`, `checks summary`, `manifest.exists`, `dry_run.status`, `next actions`.
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_telegram_bridge.py -k "onboard_command" -q`
    -> `1 passed`.

179. `P0` GitHub PR Review Comments Read/Write in Autonomous Review Stage
- Status: `done`
- Scope:
  - добавить нативные операции чтения review comments/issue comments для PR в runtime pipeline;
  - добавить возможность публиковать ответ/резюме от review stage в PR thread;
  - включить комментарии ревьюеров в `report` и `evaluate` контур.
- Done when:
  - review stage учитывает фактические reviewer comments, а не только checks;
  - pipeline может автоматически оставить structured reply в PR.
- Progress:
  - расширен `evaluate/github` контур:
    - чтение PR reviews (`/pulls/{n}/reviews`);
    - чтение PR review comments (`/pulls/{n}/comments`);
    - чтение issue comments (`/issues/{n}/comments`);
  - добавлено включение `review_feedback` в stage output и run report;
  - добавлен optional write-path:
    - `post_review_summary=true` + `pr_url|pr_number` -> публикация summary comment в PR thread;
  - добавлен контроль ошибок:
    - write-path требует review stage и PR identity;
    - GitHub posting/network ошибки возвращаются явным API error.
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "evaluate_github and (review_feedback or post_review_summary_comment or endpoint)" -q`
    -> `3 passed`;
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "auto_next or loop_tick or evaluate_github_no_checks_success_policy" -q`
    -> `16 passed`.

180. `P1` CI-First Validation Contract for DB/Multi-Container Projects
- Status: `done`
- Scope:
  - расширить task/manifest contract полями CI validation (`required_checks`, `workflow`, `service_matrix`);
  - для проектов без локального docker/toolchain автоматически выбирать CI-only validation path;
  - явный output reason: почему выбрана CI ветка и какие checks ждём.
- Done when:
  - multi-container проекты валидируются детерминированно через CI checks;
  - автономный pipeline не зависает в ожидании локального окружения.
- Progress:
  - расширен `BacklogTask` контракт:
    - `required_checks[]`, `workflow`, `service_matrix[]`,
      `validation_mode`, `validation_reason`;
  - `POST/PATCH /api/projects/{id}/autonomous/backlog[...]` теперь поддерживает новые поля;
  - добавлен автоматический `validation_mode` resolver:
    - `ci_first` при `service_matrix`/отсутствии docker CLI/нет workspace binding;
    - `local_or_ci` при доступном local runtime;
    - explicit override через `validation_mode`;
  - в task contract/report pipeline теперь включаются новые CI-first поля.
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "backlog_create_ci_first_contract_with_service_matrix or backlog_update_validation_contract_and_mode_override" -q`
    -> `2 passed`;
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "TestAutonomousPipeline or evaluate_github" -q`
    -> `52 passed`.

181. `P1` Project Environment Profile (Databases/Services/Secrets)
- Status: `done`
- Scope:
  - добавить project-level `environment_profile` (db/services/secrets contract);
  - preflight endpoint/step: проверка наличия обязательных credential aliases и service endpoints;
  - fail-fast диагностика до запуска execution/review.
- Done when:
  - перед запуском задачи оператор видит, готово ли окружение проекта;
  - missing secrets/services выявляются на preflight, а не во время долгого run.
- Progress:
  - расширен project metadata:
    - `environment_profile` (services/databases/required_credentials);
  - добавлены project API endpoints:
    - `GET /api/projects/{id}/environment`
    - `PATCH /api/projects/{id}/environment`
    - `POST /api/projects/{id}/environment/preflight`;
  - preflight проверяет:
    - наличие required credentials в credential store;
    - наличие required service/database endpoints;
  - preflight возвращает explicit readiness + missing breakdown (`credentials/services/databases`).
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "environment_profile_update_and_preflight" -q`
    -> `1 passed`;
  - regression bundle:
    - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py core/framework/server/tests/test_telegram_bridge.py -k "projects or TestAutonomousPipeline or evaluate_github or newrepo or onboard_command or repo_command" -q`
      -> `84 passed`.

182. `P1` Optional Docker-Enabled Worker Lane (Containerized)
- Status: `done`
- Scope:
  - добавить опциональный профиль worker-runtime с доступом к docker CLI (отдельный lane/profile);
  - сохранить default режим безопасным (`CI-first`, docker lane disabled by default);
  - добавить health check и явный feature flag в API/UI/Telegram status.
- Done when:
  - при необходимости локальные integration tests можно прогонять в docker-enabled lane;
  - без включения флага поведение остается прежним и безопасным.
- Progress:
  - добавлен runtime feature flag:
    - `HIVE_AUTONOMOUS_DOCKER_LANE_ENABLED` (`0` by default);
    - optional profile: `HIVE_AUTONOMOUS_DOCKER_LANE_PROFILE` (default `docker_local`);
    - optional timeout: `HIVE_AUTONOMOUS_DOCKER_LANE_HEALTHCHECK_TIMEOUT_SECONDS`.
  - добавлен docker lane health-check в API:
    - `GET /api/autonomous/ops/status` теперь возвращает:
      - `runtime.docker_lane` (`enabled`, `status`, `reason`, `ready`, `server_version/error`);
      - summary flags (`docker_lane_enabled`, `docker_lane_ready`).
  - default validation resolver ужесточен на safe-mode:
    - без enabled lane -> `validation_mode=ci_first`, `validation_reason=docker_lane_disabled`;
    - при explicit override (`validation_mode`) поведение сохраняется явным операторским решением.
  - Telegram `/status` дополнен строкой runtime lane:
    - `Docker lane: on|off (status); reason=...`.
  - Web UI (`Project Autonomous -> Ops / Loop Health`) показывает docker lane status/ready/reason.
- Validation (April 12, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_api.py -k "docker_lane or autonomous_ops_status or backlog_create_defaults_to_ci_first_when_docker_lane_disabled or backlog_create_ci_first_contract_with_service_matrix or backlog_update_validation_contract_and_mode_override" -q`
    -> `14 passed`;
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_telegram_bridge.py -k "status or toolchain or newrepo or repo or onboard" -q`
    -> `9 passed`.

183. `P1` Telegram Preset: New Repo Bootstrap Task
- Status: `done`
- Scope:
  - добавить Telegram-преднастройку задачи вида:
    `create repo -> onboard -> create first backlog task -> execute-next`;
  - включить подтверждение параметров проекта/репозитория перед запуском;
  - автоматически сохранить trace links (project, run_id, PR/report).
- Done when:
  - оператор может запустить полный bootstrap новой разработки из Telegram в одном flow;
  - результат всегда фиксируется в project artifacts/run report.
- Progress:
  - добавлена команда `/bootstrap` в Telegram bridge command registry;
  - реализован preset parser для двух режимов:
    - `newrepo`:
      `/bootstrap newrepo <name> [owner=<org>] [visibility=<..>] --task <goal> ...`
    - `repo`:
      `/bootstrap repo <url|owner/repo> --task <goal> ...`
  - добавлен confirm-first flow с inline кнопками:
    - `✅ Run Bootstrap`
    - `🚫 Cancel`;
  - после confirm выполняется автоматический pipeline:
    1) repository setup (`provision`/`bind`);
    2) project onboarding;
    3) first backlog task create;
    4) autonomous `execute-next`;
  - добавлен итоговый trace summary в Telegram:
    - `project_id`, `task_id`, `selected_task_id`, `run_id`, `terminal_status`,
      `report endpoint`, `pr url` (if available);
  - добавлены guards:
    - pending bootstrap блокирует случайные свободные сообщения до confirm/cancel;
    - stale bootstrap states очищаются TTL-prune логикой.
- Validation (April 13, 2026):
  - `./scripts/hive_ops_run.sh uv run pytest core/framework/server/tests/test_telegram_bridge.py -q`
    -> `24 passed`.

184. `P1` End-to-End Acceptance Scenario for Autonomous Delivery
- Status: `done`
- Scope:
  - добавить acceptance smoke сценарий:
    new/existing repo -> onboarding -> backlog task -> execute-next -> PR/report;
  - покрыть как минимум один real-repo sample и один template-based sample;
  - зафиксировать expected terminal states и troubleshooting.
- Done when:
  - e2e сценарий повторяем и проходит в container-first режиме;
  - регрессии выявляются автоматическим acceptance gate.
- Progress:
  - добавлен container-first e2e smoke script:
    - `scripts/autonomous_delivery_e2e_smoke.py`
    - покрывает два сценария:
      - `real_repo` (existing project/repo),
      - `template_repo` (temporary template-based project);
  - script orchestrates:
    - repository bind (optional) -> onboarding -> backlog create -> execute-next -> run report;
  - script сохраняет trace блок:
    - `project_id`, `task_id`, `selected_task_id`, `run_id`, `terminal_status`,
      `report_endpoint`, optional `pr_url`;
  - acceptance gate расширен новым toggle:
    - `HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=true`
    - добавлен optional step в `scripts/autonomous_acceptance_gate.sh`;
  - template scenario hardened:
    - если `--template-repository` не задан, используется deterministic fallback
      `https://github.com/aden-hive/hive` (trace: `template_repository_source=default_fallback`);
    - template flow не зависит от `repository/bind` и не требует GitHub token на bind-шаге;
  - onboarding-deferred path upgraded to full e2e:
    - при `ready=false` и non-strict mode flow продолжает
      `backlog_create -> execute_next -> run_report` (вместо раннего return);
  - real-repo scenario hardened for clean installs:
    - если target project отсутствует, auto-create temp real project (`e2e-real-<ts>`) + cleanup;
    - добавлен compatibility fallback для `repository/bind` при runtime API drift (`404/405`):
      сценарий продолжает onboarding/backlog/execute и фиксирует trace marker
      `repository_bind_compatibility_fallback=true`.
  - strict-terminal hardening for long-running real flows:
    - в `scripts/autonomous_delivery_e2e_smoke.py` добавлен optional patch шага
      `execution_template.github.no_checks_policy` (default `success` for smoke);
    - увеличен default terminal wait budget:
      `HIVE_DELIVERY_E2E_TERMINAL_WAIT_SECONDS=300` (раньше `60`);
    - добавлен trace marker `github_no_checks_policy`.
  - model fallback hardening for stream error events:
    - `core/framework/llm/fallback.py` теперь переключает модель, когда provider возвращает
      `StreamErrorEvent` до выдачи полезного контента;
    - добавлена дедупликация fallback provider chain по
      `(effective_model, api_base)` в:
      - `core/framework/runner/runner.py`
      - `core/framework/server/session_manager.py`.
  - runbook updated:
    - bootstrap smoke actions in Telegram checklist;
    - standalone and gate-driven e2e smoke commands.
- Validation (April 13, 2026):
  - `./scripts/hive_ops_run.sh uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py --help`
    -> usage/argparse contract confirmed;
  - `bash -n scripts/autonomous_acceptance_gate.sh`
    -> `OK`.
  - `uv run --no-project pytest scripts/tests/test_autonomous_delivery_e2e_smoke.py -q`
    -> `9 passed`;
  - live container-first run (template default fallback):
    - `./scripts/hive_ops_run.sh env HIVE_DELIVERY_E2E_BASE_URL=http://hive-core:8787 uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py`
    -> `status=ok`, `template_repo` completed with steps
      `onboarding(202) -> backlog_create(201) -> execute_next(200) -> run_report(200)`;
  - live container-first run (real+template):
    - `./scripts/hive_ops_run.sh env HIVE_DELIVERY_E2E_BASE_URL=http://hive-core:8787 HIVE_DELIVERY_E2E_REAL_REPOSITORY=https://github.com/salacoste/mcp-n8n-workflow-builder uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py`
    -> `status=ok`, both scenarios completed, temp projects cleaned up.
- Validation (April 17, 2026):
  - `uv run --no-project pytest core/tests/test_fallback_llm_provider.py core/tests/test_runner_model_fallback_chain.py scripts/tests/test_autonomous_delivery_e2e_smoke.py -q`
    -> `22 passed`;
  - strict real-repo terminal run (container-first, no cleanup):
    - `uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py --base-url http://localhost:8787 --skip-template --strict-onboarding --require-terminal-success --real-project-id e2e-real-fresh-h --real-repository https://github.com/salacoste/mcp-n8n-workflow-builder --real-agent-path exports/n8n_redirect_fixer --real-stack python --real-model-profile implementation --real-workspace-path /tmp/mcp-n8n-workflow-builder --real-issue-url https://github.com/salacoste/mcp-n8n-workflow-builder/issues/13 --max-steps 2 --terminal-max-steps 8 --terminal-poll-seconds 1.0 --no-cleanup-real-created --out-json docs/ops/acceptance-reports/e2e-real-fresh-h-terminal.json`
    -> `status=ok`, `scenarios_ok=1`, `terminal_status=completed` (`run_ab37cf395b`).

185. `P2` Telegram UX Hardening for Decision Flows
- Status: `done`
- Scope:
  - унифицировать поведение inline decision кнопок:
    single-use callbacks, явный echo выбранного варианта, блокировка повторных нажатий;
  - добавить human-readable progress hints при долгих операциях (`onboard`, `execute-next`);
  - синхронизировать UX с Web UI state transitions.
- Done when:
  - пользователь всегда видит, какой вариант выбран и что происходит дальше;
  - повторные клики не создают side effects и не путают операторский поток.
- Progress:
  - callback single-use hardening:
    - inline keyboards теперь создаются как single-use callback group;
    - после первого выбранного действия sibling callbacks в том же сообщении инвалидируются;
  - duplicate callback delivery guard:
    - добавлен dedupe по `callback_query_id` (TTL-based), повторные доставки не вызывают повторных side effects;
  - stale/replayed callback UX:
    - повторный/устаревший callback больше не отправляет spam-сообщения в чат;
    - используется `answerCallbackQuery` hint (`Already handled` / `This option is no longer active`);
  - decision echo preserved:
    - при valid выборе по кнопке сохраняется явный echo `✅ Selected: ...`.
  - long-operation progress hints:
    - `/onboard` теперь отправляет pre-flight hint `⏳ Running onboarding checks...` перед API call;
    - bootstrap flow отправляет явные hints:
      - `⏳ Step 2/4: running onboarding...`
      - `⏳ Step 4/4: running execute-next...`
- Validation (April 13, 2026):
  - `uv run --no-project pytest core/framework/server/tests/test_telegram_bridge.py -q`
    -> `27 passed` (включая новые тесты на single-use group, duplicate callback id и stale callback handling).

186. `P2` Operator Runbook: Telegram-First Autonomous Development
- Status: `done`
- Scope:
  - оформить пошаговый runbook для двух сценариев:
    `new repository` и `existing repository`;
  - добавить отдельный раздел по DB/multi-container strategy (`CI-first` + optional docker lane);
  - включить checklist запуска, валидации, rollback и incident triage.
- Done when:
  - оператор без Web UI может провести полный цикл автономной разработки через Telegram;
  - runbook покрывает штатные и аварийные сценарии.
- Progress:
  - в `docs/LOCAL_PROD_RUNBOOK.md` добавлен раздел
    `## 10) Telegram-First Autonomous Development (Operator Flow)`;
  - добавлены пошаговые operator-flows:
    - Scenario A: existing repository;
    - Scenario B: new repository;
  - добавлен отдельный блок по DB/multi-container strategy:
    - `CI-first` как default;
    - optional docker lane как controlled exception;
  - добавлены отдельные checklist и triage блоки:
    - Telegram-only run checklist;
    - rollback and incident triage.
  - добавлен terminal-side `Container-first validation bundle` в runbook:
    - bridge status, health snapshot, ops status include_runs, remediation dry-run.
  - добавлен reproducible sign-off script:
    - `scripts/telegram_operator_signoff.py`
    - генерирует artifacts:
      - `docs/ops/telegram-signoff/latest.json`
      - `docs/ops/telegram-signoff/latest.md`
    - включает machine checks (bridge/health/ops/remediation-dry-run) + manual checklist блок.
  - runbook updated с командами:
    - generate pending sign-off artifact;
    - finalize sign-off (`--manual-status pass`) после прохождения Telegram checklist.
  - live pending sign-off artifact generated (container-first):
    - `./scripts/hive_ops_run.sh env HIVE_BASE_URL=http://hive-core:8787 uv run --no-project python scripts/telegram_operator_signoff.py --project-id n8n-builder-demo-234328 --operator AB --manual-status pending`
    - outputs:
      - `docs/ops/telegram-signoff/latest.json`
      - `docs/ops/telegram-signoff/latest.md`
- Validation (April 13, 2026):
  - runbook update landed and linked to existing bridge smoke section;
  - `uv run --no-project python scripts/validate_backlog_markdown.py` -> `ok`.
  - container runtime checks:
    - `docker compose ps` -> `hive-core` / `hive-scheduler` / `hive-google-token-refresher` healthy/up;
    - `curl /api/telegram/bridge/status` -> `enabled=true`, `poller_owner=true`, `running=true`;
    - `curl /api/health` -> `telegram_bridge` snapshot present and healthy;
    - `curl /api/autonomous/ops/status?include_runs=true` -> valid ops summary shape;
    - `HIVE_AUTONOMOUS_REMEDIATE_PROJECT_ID=n8n-builder-demo-234328 HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=true ./scripts/autonomous_remediate_stale_runs.sh`
      -> `status=ok`, safe dry-run contract verified.
  - runbook sync:
    - `uv run --no-project python scripts/check_runbook_sync.py` -> `ok`.
  - script tests:
    - `uv run --no-project pytest scripts/tests/test_telegram_operator_signoff.py -q` -> `3 passed`.
  - integrated regression bundle:
    - `uv run --no-project pytest scripts/tests/test_telegram_operator_signoff.py scripts/tests/test_autonomous_delivery_e2e_smoke.py core/framework/server/tests/test_telegram_bridge.py -q`
      -> `39 passed`.
  - final live operator sign-off completed:
    - operator passed Telegram checklist (`/status`, `/sessions`, plain text, bootstrap flow);
    - logs check (`docker compose logs --since=20m hive-core`) confirms no `ERROR/Traceback` during flow;
    - final artifact refreshed with manual pass:
      - `./scripts/hive_ops_run.sh env HIVE_BASE_URL=http://hive-core:8787 uv run --no-project python scripts/telegram_operator_signoff.py --project-id n8n-builder-demo-234328 --operator AB --manual-status pass --notes "Telegram checklist passed: /status, /sessions, plain text, bootstrap flow"`
      - `docs/ops/telegram-signoff/latest.json` -> `overall_status=pass`
      - `docs/ops/telegram-signoff/latest.md` -> `overall_status=pass`.

## Execution Wave: Post-Wave Production Bugfixes

187. `P0` Fix Container-First MCP Health Summary (`--no-project`)
- Status: `done`
- Scope:
  - устранить runtime regression в `scripts/mcp_health_summary.py`, где запуск
    `uv run --no-project` падал с `ModuleNotFoundError: dotenv`;
  - сохранить container-first runbook contract без обязательной зависимости на project env.
- Done when:
  - runbook команда `./scripts/hive_ops_run.sh uv run --no-project python scripts/mcp_health_summary.py ...`
    выполняется успешно в `hive-ops` контейнере;
  - добавлен unit test на fallback path без `python-dotenv`.
- Progress:
  - `scripts/mcp_health_summary.py` обновлён:
    - `python-dotenv` import сделан optional;
    - добавлен встроенный fallback parser `.env` (`_parse_dotenv_fallback`);
    - `_load_dotenv` автоматически использует fallback при отсутствии `dotenv`.
  - добавлен unit test:
    - `scripts/tests/test_mcp_health_summary.py::test_load_dotenv_fallback_without_python_dotenv`.
- Validation (April 13, 2026):
  - `uv run --no-project pytest scripts/tests/test_mcp_health_summary.py -q` -> `8 passed`;
  - container-first regression check:
    - `./scripts/hive_ops_run.sh env HIVE_BASE_URL=http://hive-core:8787 uv run --no-project python scripts/mcp_health_summary.py --dotenv .env --since-minutes 20 --json`
    -> `summary.status=ok`, `failed=0`.

188. `P0` Fix `list_agent_tools` Credential Availability Semantics
- Status: `done`
- Scope:
  - исправить provider-level `summary` в `list_agent_tools`, чтобы `credentials_required` и
    `credentials_available` вычислялись по реальным credential specs, а не всегда возвращали
    пустые requirements / `true`;
  - исправить фильтр `credentials=available|unavailable` для multi-provider инструментов
    (пример: `send_email` через `google` ИЛИ `resend`).
- Done when:
  - `output_schema=summary` (group=`all`) показывает корректные credential requirements по провайдерам;
  - `credentials=available` считает multi-provider tool доступным, если удовлетворён хотя бы один provider path.
- Progress:
  - обновлён `tools/coder_tools_server.py`:
    - `_tool_credentials_available` теперь проверяет provider alternatives (`OR`), а не глобальный `AND`;
    - summary aggregation использует provider-specific credential mapping для вычисления `credentials_required`;
    - service breakdown (`group=<provider>, output_schema=summary`) также переведён на provider-specific
      credential resolution.
  - добавлены regression tests:
    - `test_list_agent_tools_summary_all_reports_credentials_status`;
    - `test_list_agent_tools_available_filter_supports_multi_provider_tools`
    в `tools/tests/test_coder_tools_server.py`.
- Validation (April 13, 2026):
  - `uv run --package tools pytest tools/tests/test_coder_tools_server.py -q` -> `6 passed`.

189. `P1` Silence Benign AnyIO Teardown Noise in MCP Client
- Status: `done`
- Scope:
  - убрать шумные warning-логи при teardown MCP STDIO/SSE с known anyio quirk
    (`Attempted to exit cancel scope in a different task...`);
  - сохранить warning-логирование для реальных ошибок cleanup.
- Done when:
  - при `list_agent_tools` и других короткоживущих MCP-сессиях отсутствует warning spam
    по known teardown quirk;
  - реальные ошибки cleanup продолжают логироваться как warnings.
- Progress:
  - обновлён `core/framework/runner/mcp_client.py`:
    - добавлен helper `_is_known_anyio_teardown_quirk(...)`;
    - known anyio teardown errors для session/stdio/sse downgraded до `debug`;
    - unknown cleanup errors оставлены на `warning`.
  - добавлены unit tests в `core/tests/test_mcp_client.py`:
    - `test_cleanup_demotes_known_anyio_teardown_quirk_to_debug`;
    - `test_cleanup_keeps_warning_for_real_session_close_error`.
- Validation (April 13, 2026):
  - `uv run --package framework pytest core/tests/test_mcp_client.py -q` -> `7 passed`;
  - runtime smoke (hive-core container):
    - `docker compose exec -T hive-core bash -lc 'cd /app/tools && uv run python - <<... list_agent_tools ...'`
    -> output returned without repeated `Error closing MCP session` warnings.

190. `P0` Fix Multi-Provider Availability False-Positive (`send_email`)
- Status: `done`
- Scope:
  - исправить `list_agent_tools(credentials=available)` для multi-provider tools,
    чтобы тул считался `available` только когда удовлетворён хотя бы один provider-path;
  - исключить false-positive, когда у provider credential `required=False`
    интерпретируется как "path available без ключа".
- Done when:
  - без `GOOGLE_ACCESS_TOKEN` и без `RESEND_API_KEY` tool `send_email`
    не попадает в `credentials=available` и попадает в `credentials=unavailable`;
  - поведение покрыто unit test.
- Progress:
  - `tools/coder_tools_server.py`:
    - `_tool_credentials_available` обновлён:
      provider path теперь требует присутствия всех credentials, привязанных к path;
      `required=False` больше не трактуется как path-level optional.
  - `tools/tests/test_coder_tools_server.py`:
    - добавлен regression test
      `test_list_agent_tools_multi_provider_tool_unavailable_when_no_provider_creds`.
- Validation (April 13, 2026):
  - `uv run --package tools pytest tools/tests/test_coder_tools_server.py -q` -> `7 passed`;
  - container runtime check:
    - `docker compose exec -T hive-core bash -lc 'cd /app/tools && env -u GOOGLE_ACCESS_TOKEN -u RESEND_API_KEY uv run python - <<...>>'`
    -> `available_has_send_email=False`, `unavailable_has_send_email=True`.

191. `P1` Credential Readiness Report (API + Telegram)
- Status: `done`
- Scope:
  - добавить server-side readiness endpoint с bundle-first view (`required/optional`) и provider gaps;
  - добавить операторские команды в Telegram bridge для быстрого отчёта readiness без Web UI.
- Done when:
  - доступен `GET /api/credentials/readiness?bundle=local_pro_stack`;
  - в Telegram работают `/credentials` и `/creds` с compact readiness summary.
- Progress:
  - `core/framework/server/routes_credentials.py`:
    - добавлен endpoint `GET /api/credentials/readiness`;
    - поддержан bundle `local_pro_stack` (`required` + `optional`);
    - добавлен provider-level summary (`credentials_total/available/missing`);
    - маршрут зарегистрирован до wildcard credential route.
  - `core/framework/server/telegram_bridge.py`:
    - добавлены команды `/credentials` и `/creds`;
    - добавлена кнопка `Credentials` в reply keyboard;
    - добавлен handler `_send_credentials_readiness` с вызовом локального API и compact report.
  - tests:
    - `core/framework/server/tests/test_api.py`:
      - `test_credentials_readiness_unknown_bundle`;
      - `test_credentials_readiness_local_pro_stack_shape_and_counts`;
    - `core/framework/server/tests/test_telegram_bridge.py`:
      - `test_credentials_commands_dispatch_readiness`.
- Validation (April 13, 2026):
  - `uv run --package framework pytest core/framework/server/tests/test_api.py -k "credentials_readiness" -q` -> `2 passed`;
  - `uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q` -> `28 passed`;
 - runtime container check:
   - `curl 'http://localhost:8787/api/credentials/readiness?bundle=local_pro_stack'`
     -> `summary.required_missing=0`, response shape valid.

192. `P1` Credential Readiness Operator Widget (Web UI)
- Status: `done`
- Scope:
  - добавить в `workspace` операторский индикатор readiness рядом с control buttons;
  - показать compact status по required credentials (`available/total`) и состояние ошибки;
  - добавить ручной refresh и автообновление после сохранения credentials.
- Done when:
  - оператор в Web UI видит текущий readiness без открытия API/Telegram;
  - после `Credentials` save индикатор обновляется автоматически.
- Progress:
  - `core/frontend/src/api/credentials.ts`:
    - добавлены typed модели readiness (`CredentialReadinessResponse` и связанные типы);
    - добавлен метод `credentialsApi.readiness(bundle?)`.
  - `core/frontend/src/pages/workspace.tsx`:
    - добавлены state/loading/error для readiness snapshot;
    - добавлен `refreshCredentialReadiness()` + initial load effect;
    - добавлен TopBar badge `Cred X/Y` с цветовой индикацией `ready/error/missing`;
    - добавлена кнопка refresh readiness;
    - в `CredentialsModal.onCredentialChange` добавлен auto-refresh readiness.
- Validation (April 13, 2026):
  - typecheck: `cd core/frontend && npx tsc -b` -> `pass`;
 - container-first frontend build:
   - `docker run --rm -v "$PWD":/work -w /work/core/frontend node:22-bookworm bash -lc 'npm ci --no-audit --no-fund && npm run build'`
      -> `pass` (`vite build` success, chunks generated).

193. `P1` Credentials CTA Hardening (Web UI)
- Status: `done`
- Scope:
  - сделать предупреждение о missing required credentials видимым прямо на основной кнопке `Credentials`;
  - добавить счетчик `required_missing` на CTA, чтобы оператор видел проблему даже без `xl` readiness badge.
- Done when:
  - кнопка `Credentials` показывает count badge при `required_missing > 0`;
  - у кнопки есть contextual tone/error state и tooltip с деталями readiness.
- Progress:
  - `core/frontend/src/pages/workspace.tsx`:
    - добавлен `readinessMissingRequiredCount` derived state;
    - `Credentials` кнопка получила dynamic tone class (`error` / `missing` / normal);
    - добавлен inline count badge на кнопке при missing required;
    - `title` кнопки привязан к readiness summary/details.
- Validation (April 13, 2026):
  - container-first frontend build:
    - `docker run --rm -v "$PWD":/work -w /work/core/frontend node:22-bookworm bash -lc 'npm ci --no-audit --no-fund && npm run build'`
      -> `pass` (`vite build` success).

194. `P1` Credential Readiness Detail Modal (Web UI)
- Status: `done`
- Scope:
  - добавить детальный operator modal по readiness (required/optional/provider gaps);
  - открыть modal напрямую из TopBar readiness badge;
  - дать быстрый переход в `Credentials` modal для исправления missing keys.
- Done when:
  - оператор кликает `Cred X/Y` и видит детализированную readiness-карту;
  - доступен быстрый action: `Refresh` и `Open Credentials`.
- Progress:
  - `core/frontend/src/pages/workspace.tsx`:
    - добавлен state `credentialReadinessOpen`;
    - `Cred X/Y` в TopBar переведён в action button (open modal);
    - добавлен modal `Credential Readiness` с секциями:
      - summary (`required/optional`),
      - required env vars (`ok/missing`),
      - optional env vars (`ok/not set`),
      - provider gaps (`available/total`, missing env list);
    - добавлены CTA в modal footer: `Refresh`, `Open Credentials`.
- Validation (April 13, 2026):
  - container-first frontend build:
    - `docker run --rm -v "$PWD":/work -w /work/core/frontend node:22-bookworm bash -lc 'npm ci --no-audit --no-fund && npm run build'`
      -> `pass` (`vite build` success).

195. `P1` Credential Readiness Provider-Gap Noise Reduction (Web UI)
- Status: `done`
- Scope:
  - снизить шум в `Provider Gaps`: по умолчанию показывать только gaps, релевантные текущему readiness bundle;
  - оставить возможность оператору открыть полный список provider gaps on-demand.
- Done when:
  - `Credential Readiness` modal показывает bundle-scoped provider gaps по умолчанию;
  - доступен toggle `Show all (+N)` / `Show bundle-only`.
- Progress:
  - `core/frontend/src/pages/workspace.tsx`:
    - добавлен bundle env-var set (`required + optional`);
    - `Provider Gaps` теперь фильтруется до `credentials_missing > 0` и bundle-related env vars;
    - добавлен toggle для переключения full vs bundle-only provider list;
    - добавлен empty-state: `No provider gaps for this bundle`.
- Validation (April 14, 2026):
  - container-first frontend build:
    - `docker run --rm -v "$PWD":/work -w /work/core/frontend node:22-bookworm bash -lc 'npm ci --no-audit --no-fund && npm run build'`
      -> `pass` (`vite build` success).

196. `P1` Data Button Fallback UX (Container-Safe)
- Status: `done`
- Scope:
  - устранить silent-fail при нажатии `Data` в `Workspace` TopBar;
  - сделать backend reveal endpoint container-safe: возвращать путь даже при невозможности открыть file manager;
  - дать пользователю явный fallback в UI (path + reason) вместо "ничего не произошло".
- Done when:
  - `Data` больше не молчит при ошибке launcher;
  - при launcher failure UI показывает понятный fallback и путь к session folder.
- Progress:
  - `core/framework/server/routes_sessions.py`:
    - `POST /api/sessions/{id}/reveal` переведен на structured result:
      - success: `{path, opened: true, launcher}`;
      - launcher failure: `{path, opened: false, error, launcher}` (`200`, не `500`);
    - добавлен fallback на stderr/stdout/exit code.
  - `core/framework/server/tests/test_api.py`:
    - добавлены тесты:
      - `test_reveal_session_folder_returns_fallback_when_launcher_fails`;
      - `test_reveal_session_folder_returns_opened_true_on_success`.
  - `core/frontend/src/api/sessions.ts`:
    - обновлен response type для `revealFolder`.
  - `core/frontend/src/pages/workspace.tsx`:
    - `Data` button now handles fallback:
      - при `opened=false` показывает alert с path/reason;
      - path копируется в clipboard (best-effort).
- Validation (April 14, 2026):
  - backend tests:
    - `uv run --package framework pytest core/framework/server/tests/test_api.py -k "reveal_session_folder" -q`
      -> `2 passed`;
  - container-first frontend build:
    - `docker run --rm -v "$PWD":/work -w /work/core/frontend node:22-bookworm bash -lc 'npm ci --no-audit --no-fund && npm run build'`
      -> `pass` (`vite build` success).

197. `P1` Session Data Export Download (Container-First)
- Status: `done`
- Scope:
  - добавить container-safe альтернативу открытию локальной папки сессии;
  - реализовать backend endpoint для скачивания данных сессии архивом;
  - добавить кнопку `Export` в Web UI рядом с `Data`.
- Done when:
  - оператор может скачать `.zip` с данными сессии прямо из браузера в Docker-среде;
  - сценарий не зависит от GUI launcher (`xdg-open/open/explorer`).
- Progress:
  - `core/framework/server/routes_sessions.py`:
    - добавлен helper `_resolve_session_storage_folder(...)` (единый путь для live/cold и `queen_resume_from`);
    - добавлен endpoint `GET /api/sessions/{session_id}/export`;
    - реализована упаковка session folder в zip + streaming response (`Content-Disposition: attachment`).
  - `core/framework/server/tests/test_api.py`:
    - добавлены тесты:
      - `test_export_session_folder_returns_zip_payload`;
      - `test_export_session_folder_uses_resume_storage_id`;
      - `test_export_session_folder_returns_404_when_folder_missing`.
  - `core/frontend/src/api/sessions.ts`:
    - добавлен `sessionsApi.exportArchive(sessionId)` (blob + filename parsing).
  - `core/frontend/src/pages/workspace.tsx`:
    - добавлена кнопка `Export` в TopBar для active session;
    - реализован browser download flow через object URL.
- Validation (April 14, 2026):
  - backend tests:
    - `uv run --package framework pytest core/framework/server/tests/test_api.py -k "reveal_session_folder or export_session_folder" -q`
      -> `5 passed`;
  - container-first frontend build:
    - `docker run --rm -v "$PWD":/work -w /work/core/frontend node:22-bookworm bash -lc 'npm ci --no-audit --no-fund && npm run build'`
      -> `pass` (`vite build` success);
  - runtime smoke:
    - `docker compose up -d --build hive-core` -> `pass`;
    - `curl -sS http://localhost:8787/api/health` -> `status=ok`;
    - `GET /api/sessions/nonexistent/export` -> `404` (endpoint active).

198. `P2` Scheduler Status Noise Reduction in Docker Snapshot
- Status: `done`
- Scope:
  - убрать ложные `error: crontab is required` из acceptance snapshot в container-first окружении;
  - скорректировать summary parser, чтобы `not-supported` не трактовался как `installed`.
- Done when:
  - `acceptance_scheduler_snapshot.sh` в Docker выводит clean status без error-шума при отсутствии `crontab`;
  - `acceptance_ops_summary.py` возвращает `not-supported` для cron scheduler status в таком окружении.
- Progress:
  - `scripts/_cron_job_lib.sh`:
    - добавлен helper `hive_cron_has_crontab()`.
  - `scripts/status_acceptance_gate_cron.sh`:
    - добавлен graceful fallback `not-supported: crontab not found`.
  - `scripts/status_acceptance_weekly_cron.sh`:
    - добавлен graceful fallback `not-supported: crontab not found`.
  - `scripts/status_autonomous_loop_cron.sh`:
    - добавлен graceful fallback `not-supported: crontab not found`.
  - `scripts/acceptance_ops_summary.py`:
    - `_scheduler_status()` теперь отдельно обрабатывает:
      - `not-supported:*` -> `not-supported`;
      - `error:*` -> `error`;
      - вместо старого fallback `installed` для всего кроме `not-installed`.
  - `scripts/tests/test_acceptance_ops_summary.py`:
    - добавлен тест `test_scheduler_status_parses_not_supported`.
- Validation (April 14, 2026):
  - targeted tests:
    - `uv run pytest scripts/tests/test_acceptance_ops_summary.py -q` -> `4 passed`;
  - ops summary runtime check:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/acceptance_ops_summary.py --json`
      -> `scheduler_*_cron = not-supported`;
  - acceptance self-check:
    - `./scripts/hive_ops_run.sh ./scripts/acceptance_toolchain_self_check.sh` -> `Self-check summary: ok=20 failed=0`.

199. `P1` Runtime Parity Auto Base-URL Resolution (Docker Ops)
- Status: `done`
- Scope:
  - устранить flaky failure `runtime parity check` в `hive-ops` контексте, когда `localhost:8787` недоступен;
  - добавить deterministic выбор доступного Hive API base URL для parity smoke.
- Done when:
  - `scripts/check_runtime_parity.sh` автоматически выбирает доступный endpoint (`localhost`/`hive-core`);
  - `acceptance_toolchain_self_check_deep.sh` проходит с `runtime parity check` в green.
- Progress:
  - `scripts/check_runtime_parity.sh`:
    - добавлен `CORE_PORT` и resolver `resolve_base_url()`;
    - порядок probe:
      1) `HIVE_BASE_URL` (если задан),
      2) `http://localhost:${CORE_PORT}`,
      3) `http://hive-core:${CORE_PORT}`;
    - добавлен info-line: `[info] runtime parity base_url=<resolved>`.
- Validation (April 14, 2026):
  - deep self-check:
    - `./scripts/hive_ops_run.sh ./scripts/acceptance_toolchain_self_check_deep.sh`
      -> `Self-check summary: ok=22 failed=0`;
    - `runtime parity check passed` with resolved base URL:
      `http://hive-core:8787`.

200. `P1` Autonomous Delivery E2E Smoke Verification (Docker Ops)
- Status: `done`
- Scope:
  - подтвердить end-to-end автономный delivery контур через container-first smoke для:
    - template scenario,
    - real repository scenario (existing project).
- Done when:
  - `autonomous_delivery_e2e_smoke.py` проходит для template и real сценариев через `hive-ops` с `HIVE_DELIVERY_E2E_BASE_URL=http://hive-core:8787`;
  - после прогона нет runtime ошибок в `hive-core` logs.
- Progress:
  - template smoke:
    - `./scripts/hive_ops_run.sh env HIVE_DELIVERY_E2E_BASE_URL=http://hive-core:8787 uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py --skip-real --max-steps 2`
    - result: `status=ok`, `scenarios_ok=1`, flow `onboarding -> backlog_create -> execute_next -> run_report`.
  - real-repo smoke:
    - `./scripts/hive_ops_run.sh env HIVE_DELIVERY_E2E_BASE_URL=http://hive-core:8787 uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py --skip-template --real-project-id n8n-builder-demo-234328 --real-repository https://github.com/salacoste/mcp-n8n-workflow-builder --max-steps 2`
    - result: `status=ok`, `scenarios_ok=1`, flow `repository_bind -> onboarding -> backlog_create -> execute_next -> run_report`.
  - post-check logs:
    - `docker logs --since 5m hive-core | rg "ERROR|Traceback|Exception"` -> no matches.

201. `P1` Operator Profile Wrapper (Daily/Deep/Dry-Run)
- Status: `done`
- Scope:
  - добавить единый operator entrypoint для контейнер-first autonomous operations;
  - зафиксировать режимы ежедневной работы и deep валидации без ручного набора длинных command chains.
- Done when:
  - есть один скрипт с режимами `daily`, `deep`, `dry-run` и project scoping;
  - runbook + acceptance map документируют operator profile usage;
  - guardrail checks (runbook/docs/self-check script) остаются green.
- Progress:
  - добавлен `scripts/autonomous_operator_profile.sh`:
    - `daily`: `hive_ops_preflight` -> acceptance preset `strict` -> ops summary JSON;
    - `deep`: `hive_ops_preflight` -> deep self-check -> acceptance preset `full-deep` -> ops summary JSON;
    - `dry-run`: safe preview (`--print-env-only`) для strict/full-deep + ops summary JSON;
    - поддержка `--project`, `--base-url`, `--print-plan`.
  - `docs/ops/acceptance-automation-map.md`:
    - добавлен раздел про `autonomous_operator_profile.sh` в container-first entrypoints;
    - обновлен `Quick Start` с operator daily/deep/dry-run командами.
  - `docs/LOCAL_PROD_RUNBOOK.md`:
    - добавлен блок `Operator profile wrapper (container-first)` + описание режимов.
  - `scripts/acceptance_toolchain_self_check.sh`:
    - shell syntax bundle включает `scripts/autonomous_operator_profile.sh`.
  - `scripts/tests/test_acceptance_toolchain_self_check_script.py`:
    - добавлена проверка присутствия `scripts/autonomous_operator_profile.sh` в self-check syntax bundle.
- Validation (April 14, 2026):
  - shell syntax:
    - `bash -n scripts/autonomous_operator_profile.sh scripts/acceptance_toolchain_self_check.sh` -> `pass`;
  - unit:
    - `uv run pytest scripts/tests/test_acceptance_toolchain_self_check_script.py -q` -> `1 passed`;
  - dry-run smoke:
    - `./scripts/autonomous_operator_profile.sh --mode dry-run --project n8n-builder-demo-234328` -> `pass`;
  - docs guardrails:
    - `uv run python scripts/check_runbook_sync.py` -> `pass`;
    - `uv run python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `uv run python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`.

202. `P1` Operator Daily Profile Live Validation + Threshold Tuning
- Status: `done`
- Scope:
  - прогнать `autonomous_operator_profile --mode daily` на реальном проекте;
  - устранить false-negative в strict gate для локального container runtime
    (ожидаемый `loop_stale`/`no_progress_projects` без постоянного heartbeat cadence).
- Done when:
  - `daily` профиль проходит end-to-end (`exit 0`) на целевом проекте;
  - daily mode явно использует operator-safe health overrides;
  - behavior зафиксирован в docs + regression test.
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - daily mode updated:
      - `HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE=true`;
      - `HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS=${...:-1}`;
      - strict gate step label обновлен до
        `strict preset, operator-safe health thresholds`.
  - `docs/LOCAL_PROD_RUNBOOK.md`:
    - в блоке operator profile добавлено описание daily health overrides.
  - `docs/ops/acceptance-automation-map.md`:
    - добавлена заметка про daily operator-safe overrides.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - добавлен test coverage на наличие daily overrides в скрипте.
- Validation (April 14, 2026):
  - live run:
    - `./scripts/autonomous_operator_profile.sh --mode daily --project n8n-builder-demo-234328`
      -> `pass` (`[ok] operator profile completed`);
  - targeted tests:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py scripts/tests/test_acceptance_toolchain_self_check_script.py -q`
      -> `2 passed`;
  - docs/runbook guardrails:
    - `uv run python scripts/check_runbook_sync.py` -> `pass`;
    - `uv run python scripts/check_acceptance_docs_navigation.py` -> `pass`.

203. `P1` Deep Profile Determinism + Operator-Safe Health Alignment
- Status: `done`
- Scope:
  - устранить flaky падение `deep` профиля из-за env contamination в preset smoke;
  - выровнять `deep` gate с operator-safe health порогами (как в daily) для локального container runtime;
  - закрепить поведение regression-тестами.
- Done when:
  - preset smoke гарантированно deterministic при загрязненном окружении;
  - `autonomous_operator_profile --mode deep` стабильно проходит на целевом проекте;
  - есть test coverage на `deep` operator-safe overrides.
- Progress:
  - `scripts/acceptance_gate_presets.sh`:
    - режимы `fast/strict/full/full-deep` переведены на явные `export` значений критичных toggles;
    - исключено наследование случайных env значений.
  - `scripts/acceptance_gate_presets_smoke.sh`:
    - расширен clean-env wrapper (`-u HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE`, `-u HIVE_DELIVERY_E2E_SKIP_REAL`).
  - `scripts/check_acceptance_preset_smoke_determinism.sh`:
    - добавлены contamination checks для delivery-e2e toggles.
  - `scripts/tests/test_acceptance_gate_presets_smoke_behavior.py`:
    - добавлены assertions на отсутствие утечек delivery-e2e vars в `fast/strict` и наличие в `full-deep`.
  - `scripts/tests/test_acceptance_gate_presets_smoke_script.py`:
    - добавлены проверки clean-env unsets для delivery-e2e vars.
  - `scripts/autonomous_operator_profile.sh`:
    - `deep` mode gate запускается с operator-safe health overrides:
      - `HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE=true`;
      - `HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS=${...:-1}`.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - добавлен отдельный regression-тест на `deep` mode operator-safe overrides.
- Validation (April 14, 2026):
  - preset tests:
    - `uv run pytest scripts/tests/test_acceptance_gate_presets.py scripts/tests/test_acceptance_gate_presets_smoke_behavior.py scripts/tests/test_acceptance_gate_presets_smoke_script.py scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `13 passed`;
  - deterministic smoke:
    - `./scripts/check_acceptance_preset_smoke_determinism.sh` -> `pass`;
  - live deep run:
    - `./scripts/autonomous_operator_profile.sh --mode deep --project n8n-builder-demo-234328`
      -> `pass` (`[ok] operator profile completed`).

204. `P1` Daily Profile Auto-Remediation for Stale Runs
- Status: `done`
- Scope:
  - убрать ручной шаг remediation перед `daily` profile;
  - автоматически выполнять remediation stale runs до strict gate;
  - сохранить управляемость через env toggles.
- Done when:
  - `daily` профиль самостоятельно обрабатывает stale runs перед health-check;
  - можно отключить auto-remediation или сменить action через env.
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - добавлены env controls:
      - `HIVE_OPERATOR_AUTO_REMEDIATE_STALE` (default `true`);
      - `HIVE_OPERATOR_REMEDIATE_ACTION` (default `escalated`);
    - `daily` mode flow обновлен:
      - `preflight -> stale remediation (apply) -> strict gate -> ops summary`;
    - remediation запускается project-scoped с confirm/apply:
      - `HIVE_AUTONOMOUS_REMEDIATE_PROJECT_ID=<project>`;
      - `HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=false`;
      - `HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=true`.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - расширен regression coverage на `daily` remediation block/envs.
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md` (profile modes section);
    - `docs/ops/acceptance-automation-map.md` (container-first entrypoints).
- Validation (April 14, 2026):
  - unit:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `2 passed`;
  - guardrails/docs:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`;
  - live daily run:
    - `./scripts/autonomous_operator_profile.sh --mode daily --project n8n-builder-demo-234328`
      -> `pass`;
    - в логе подтвержден автоматический шаг:
      `Stale runs remediation (apply before strict gate)`.

205. `P1` Deep Profile Optional Auto-Remediation Hook
- Status: `done`
- Scope:
  - добавить опциональный remediation pre-step и для `deep` режима;
  - по умолчанию не менять текущее поведение `deep` (remediation off);
  - документировать управление флагом.
- Done when:
  - `deep` поддерживает env-toggle для apply-remediation перед `full-deep` gate;
  - default behavior сохраняется (`deep` без remediation, если флаг не включен).
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - добавлен env toggle `HIVE_OPERATOR_DEEP_AUTO_REMEDIATE_STALE` (default `false`);
    - при `true` выполняется шаг:
      `Stale runs remediation (apply before full-deep gate)` с project-scoped apply/confirm.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - расширен regression coverage для deep remediation toggle/block.
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md` (profile modes);
    - `docs/ops/acceptance-automation-map.md` (container-first entrypoints).
- Validation (April 14, 2026):
  - unit:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `2 passed`;
  - docs guardrails:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`;
  - live deep run (feature enabled):
    - `HIVE_OPERATOR_DEEP_AUTO_REMEDIATE_STALE=true ./scripts/autonomous_operator_profile.sh --mode deep --project n8n-builder-demo-234328`
      -> `pass`;
    - лог содержит шаг:
      `Stale runs remediation (apply before full-deep gate)`.

206. `P1` Operator Profile CLI Remediation Overrides
- Status: `done`
- Scope:
  - добавить удобные run-scoped CLI флаги для remediation без env-переменных;
  - обеспечить приоритет CLI override над `HIVE_OPERATOR_*` env;
  - закрепить это поведенческими тестами.
- Done when:
  - `autonomous_operator_profile.sh` поддерживает:
    - `--remediate`
    - `--no-remediate`;
  - в output видно effective remediation toggles;
  - deep/daily behavior можно переключать в одном запуске без изменения `.env`.
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - добавлены CLI flags `--remediate` / `--no-remediate`;
    - добавлена boolean validation (`normalize_bool`) для remediation toggles;
    - реализован run-scoped override с приоритетом над env:
      - `daily_auto_remediate_stale=<effective>`;
      - `deep_auto_remediate_stale=<effective>`;
    - usage/examples обновлены.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - добавлены поведенческие тесты:
      - `--remediate` принудительно включает remediation даже при env=false;
      - `--no-remediate` принудительно выключает remediation даже при env=true.
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md` (CLI overrides section);
    - `docs/ops/acceptance-automation-map.md` (entrypoint flags).
- Validation (April 14, 2026):
  - unit:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `4 passed`;
  - docs guardrails:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`;
  - print-plan behavior check:
    - `HIVE_OPERATOR_AUTO_REMEDIATE_STALE=false HIVE_OPERATOR_DEEP_AUTO_REMEDIATE_STALE=false ./scripts/autonomous_operator_profile.sh --mode deep --project n8n-builder-demo-234328 --print-plan --remediate`
      -> `pass`, output includes:
      - `daily_auto_remediate_stale=true`
      - `deep_auto_remediate_stale=true`.

207. `P1` Operator Profile CLI Remediation Action Override
- Status: `done`
- Scope:
  - добавить run-scoped CLI override для remediation action без env-переменных;
  - валидировать action на уровне operator profile (`escalated|failed`);
  - закрепить поведение unit-тестами и docs.
- Done when:
  - `autonomous_operator_profile.sh` поддерживает:
    - `--remediate-action <escalated|failed>`;
  - CLI value имеет приоритет над `HIVE_OPERATOR_REMEDIATE_ACTION`;
  - invalid action возвращает явную ошибку (`exit 2`).
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - добавлен CLI аргумент `--remediate-action`;
    - добавлена валидация `normalize_remediate_action`;
    - реализован override precedence:
      - env `HIVE_OPERATOR_REMEDIATE_ACTION` -> default/effective;
      - CLI `--remediate-action` -> final effective value;
    - usage/examples обновлены.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - добавлены тесты:
      - `test_operator_profile_cli_remediate_action_override_is_applied`;
      - `test_operator_profile_cli_rejects_invalid_remediate_action`.
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md` (CLI overrides section);
    - `docs/ops/acceptance-automation-map.md` (entrypoint flags).
- Validation (April 14, 2026):
  - unit:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `6 passed`;
  - docs guardrails:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`;
  - print-plan action override check:
    - `./scripts/autonomous_operator_profile.sh --mode daily --project n8n-builder-demo-234328 --print-plan --remediate-action failed`
      -> `pass`, output includes:
      - `remediate_action=failed`
      - remediation command with `HIVE_AUTONOMOUS_REMEDIATE_ACTION=failed`.

208. `P1` Operator Profile Mode-Specific CLI Remediation Overrides
- Status: `done`
- Scope:
  - добавить раздельные CLI overrides для daily/deep remediation;
  - сохранить общий override (`--remediate` / `--no-remediate`) и сделать mode-specific overrides приоритетнее;
  - покрыть поведенческими тестами.
- Done when:
  - доступны флаги:
    - `--daily-remediate` / `--no-daily-remediate`
    - `--deep-remediate` / `--no-deep-remediate`;
  - mode-specific overrides корректно переопределяют общий override в рамках одного запуска.
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - добавлены новые CLI flags для daily/deep remediation;
    - добавлена normalisation/validation mode-specific overrides;
    - обновлена логика effective toggles:
      - base from env;
      - optional global override;
      - final per-mode overrides (highest priority);
    - usage/examples обновлены.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - добавлены поведенческие тесты на precedence:
      - global `--remediate` + `--no-deep-remediate` => daily=true, deep=false;
      - global `--no-remediate` + `--daily-remediate` => daily=true, deep=false.
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md` (CLI overrides section);
    - `docs/ops/acceptance-automation-map.md` (entrypoint flags).
- Validation (April 14, 2026):
  - unit:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `8 passed`;
  - docs guardrails:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`;
  - print-plan behavior checks:
    - `./scripts/autonomous_operator_profile.sh --mode deep --project n8n-builder-demo-234328 --print-plan --remediate --no-deep-remediate`
      -> `pass`, output includes:
      - `daily_auto_remediate_stale=true`
      - `deep_auto_remediate_stale=false`;
    - `./scripts/autonomous_operator_profile.sh --mode daily --project n8n-builder-demo-234328 --print-plan --no-remediate --daily-remediate`
      -> `pass`, output includes:
      - `daily_auto_remediate_stale=true`
      - `deep_auto_remediate_stale=false`.

209. `P1` Operator Project Health Profile CLI
- Status: `done`
- Scope:
  - добавить единый CLI флаг для выбора health-threshold профиля;
  - заменить ручное управление набором `HIVE_AUTONOMOUS_HEALTH_*` переменных при типовых режимах;
  - сохранить возможность точечного env override.
- Done when:
  - `autonomous_operator_profile.sh` поддерживает:
    - `--project-health-profile <prod|strict|relaxed>`;
  - профиль вычисляет effective thresholds:
    - `health_max_stuck_runs`
    - `health_max_no_progress_projects`
    - `health_allow_loop_stale`;
  - эти значения прокидываются в acceptance gate в daily/deep.
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - добавлен `PROJECT_HEALTH_PROFILE` (`HIVE_OPERATOR_PROJECT_HEALTH_PROFILE`, default `prod`);
    - добавлен parser/validator `normalize_project_health_profile`;
    - реализован mapping:
      - `prod`: `0 / 1 / true`
      - `strict`: `0 / 0 / false`
      - `relaxed`: `2 / 2 / true`;
    - добавлен вывод effective health параметров в header;
    - daily/deep gate now receives:
      - `HIVE_AUTONOMOUS_HEALTH_MAX_STUCK_RUNS`
      - `HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS`
      - `HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE`.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - добавлены tests:
      - strict profile thresholds;
      - relaxed profile thresholds;
      - invalid profile reject (`exit 2`).
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md` (profile modes + CLI overrides);
    - `docs/ops/acceptance-automation-map.md` (operator health profiles + flag).
- Validation (April 14, 2026):
  - unit:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `11 passed`;
  - docs guardrails:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`;
  - print-plan profile checks:
    - `./scripts/autonomous_operator_profile.sh --mode daily --project n8n-builder-demo-234328 --print-plan --project-health-profile strict`
      -> `health_max_stuck_runs=0`, `health_max_no_progress_projects=0`, `health_allow_loop_stale=false`;
    - `./scripts/autonomous_operator_profile.sh --mode daily --project n8n-builder-demo-234328 --print-plan --project-health-profile relaxed`
      -> `health_max_stuck_runs=2`, `health_max_no_progress_projects=2`, `health_allow_loop_stale=true`.

210. `P1` Operator Fast-Path Flags (`--skip-preflight`, `--skip-self-check`)
- Status: `done`
- Scope:
  - добавить ускоренный operator path для ops-only запусков без изменения безопасных дефолтов;
  - поддержать пропуск preflight и deep self-check через явные CLI флаги;
  - сохранить прозрачность поведения в выводе profile header.
- Done when:
  - `autonomous_operator_profile.sh` поддерживает:
    - `--skip-preflight`
    - `--skip-self-check`;
  - deep mode может пропускать preflight/self-check по флагам;
  - при `--skip-self-check` в non-deep режиме выводится info, что флаг не влияет.
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - добавлены CLI flags `--skip-preflight`, `--skip-self-check`;
    - добавлены helper steps:
      - `run_preflight_if_enabled()`
      - `run_deep_self_check_if_enabled()`;
    - profile header расширен:
      - `skip_preflight=<bool>`
      - `skip_self_check=<bool>`;
    - для mode!=deep добавлен info-line:
      - `[info] --skip-self-check has no effect in mode=<mode>`.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - добавлены tests:
      - `test_operator_profile_skip_preflight_and_self_check_flags_skip_steps`;
      - `test_operator_profile_skip_self_check_info_for_non_deep_mode`.
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md` (CLI overrides section);
    - `docs/ops/acceptance-automation-map.md` (operator entrypoint flags).
- Validation (April 14, 2026):
  - unit:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `13 passed`;
  - docs guardrails:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`;
  - print-plan checks:
    - `./scripts/autonomous_operator_profile.sh --mode deep --project n8n-builder-demo-234328 --print-plan --skip-preflight --skip-self-check`
      -> `pass`, output includes skip-lines for preflight and deep self-check;
    - `./scripts/autonomous_operator_profile.sh --mode daily --project n8n-builder-demo-234328 --print-plan --skip-self-check`
      -> `pass`, output includes:
      `[info] --skip-self-check has no effect in mode=daily`.

211. `P1` Operator `--ops-summary-only` Fast Monitoring Mode
- Status: `done`
- Scope:
  - добавить режим сверхбыстрого мониторинга без pipeline стадий;
  - запускать только итоговый `acceptance_ops_summary.py --json`;
  - исключить preflight/self-check/remediation/acceptance gate в рамках одного запуска.
- Done when:
  - `autonomous_operator_profile.sh` поддерживает:
    - `--ops-summary-only`;
  - при включении режима выполняется только `Ops summary (json)` шаг;
  - вывод явно сообщает о пропущенных стадиях.
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - добавлен CLI flag `--ops-summary-only`;
    - header расширен полем `ops_summary_only=<bool>`;
    - добавлен early-return fast path:
      - message: `ops-summary-only mode: skipping preflight, deep self-check, remediation, acceptance gate`;
      - выполняется только `run_cmd "Ops summary (json)" ...`;
      - затем immediate `[ok] operator profile completed`.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - добавлен поведенческий тест `test_operator_profile_ops_summary_only_skips_pipeline_steps`.
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md` (CLI overrides section);
    - `docs/ops/acceptance-automation-map.md` (operator entrypoint flags).
- Validation (April 14, 2026):
  - unit:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `14 passed`;
  - docs guardrails:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`;
  - print-plan check:
    - `./scripts/autonomous_operator_profile.sh --mode deep --project n8n-builder-demo-234328 --print-plan --ops-summary-only`
      -> `pass`, output includes:
      - `ops_summary_only=true`
      - skip message for preflight/self-check/remediation/gate
      - only `Ops summary (json)` step.

212. `P1` Operator `--acceptance-preset` Override
- Status: `done`
- Scope:
  - добавить явный выбор acceptance preset в operator profile, независимо от `mode`;
  - поддержать preset override в daily/deep gate и в dry-run preview;
  - валидировать значения preset.
- Done when:
  - `autonomous_operator_profile.sh` поддерживает:
    - `--acceptance-preset <fast|strict|full|full-deep>`;
  - daily/deep gate запускаются с выбранным preset;
  - dry-run при override показывает preview только выбранного preset.
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - добавлен env fallback `HIVE_OPERATOR_ACCEPTANCE_PRESET`;
    - добавлен CLI flag `--acceptance-preset`;
    - добавлен validator `normalize_acceptance_preset`;
    - добавлены effective fields:
      - `acceptance_preset_daily`
      - `acceptance_preset_deep`;
    - daily/deep gate switched to dynamic preset command:
      `./scripts/acceptance_gate_presets.sh "$<effective_preset>" --project ...`;
    - dry-run behavior:
      - with override: preview only selected preset;
      - without override: legacy dual preview (`strict` + `full-deep`).
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - added tests:
      - `test_operator_profile_acceptance_preset_override_applies_to_daily_gate`
      - `test_operator_profile_acceptance_preset_override_dry_run_previews_only_selected_preset`
      - `test_operator_profile_rejects_invalid_acceptance_preset`
    - existing static string checks updated to parameterized gate labels.
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md` (CLI overrides section);
    - `docs/ops/acceptance-automation-map.md` (operator entrypoint flags).
- Validation (April 14, 2026):
  - unit:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `17 passed`;
  - docs guardrails:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`;
  - print-plan checks:
    - `./scripts/autonomous_operator_profile.sh --mode daily --project n8n-builder-demo-234328 --print-plan --acceptance-preset full`
      -> `acceptance_preset_daily=full`, gate command uses `full`;
    - `./scripts/autonomous_operator_profile.sh --mode dry-run --project n8n-builder-demo-234328 --print-plan --acceptance-preset fast`
      -> only `Acceptance fast preset (env preview)` is shown.

213. `P1` Operator `--acceptance-extra-args` Passthrough
- Status: `done`
- Scope:
  - добавить run-scoped passthrough дополнительных аргументов в acceptance preset launcher;
  - поддержать одинаковый passthrough для daily/deep gate и dry-run preview;
  - оставить поведение явным через header fields.
- Done when:
  - `autonomous_operator_profile.sh` поддерживает:
    - `--acceptance-extra-args "<...>"`;
  - extra args корректно прокидываются в
    `./scripts/acceptance_gate_presets.sh ... -- <args>`.
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - добавлен env fallback `HIVE_OPERATOR_ACCEPTANCE_EXTRA_ARGS`;
    - добавлен CLI flag `--acceptance-extra-args`;
    - добавлен parsing в array `ACCEPTANCE_EXTRA_ARGS` (word-split input string);
    - добавлены helpers:
      - `run_acceptance_gate_with_preset()`
      - `run_acceptance_preset_preview()`;
    - header расширен:
      - `acceptance_extra_args_raw`
      - `acceptance_extra_args_count`.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - added tests:
      - `test_operator_profile_acceptance_extra_args_are_forwarded_to_gate_command`;
      - `test_operator_profile_acceptance_extra_args_are_forwarded_to_dry_run_preview`.
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md` (CLI overrides section);
    - `docs/ops/acceptance-automation-map.md` (operator entrypoint flags).
- Validation (April 14, 2026):
  - unit:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `19 passed`;
  - docs guardrails:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`;
  - print-plan checks:
    - `./scripts/autonomous_operator_profile.sh --mode daily --project n8n-builder-demo-234328 --print-plan --acceptance-preset full --acceptance-extra-args "--summary-json --skip-telegram"`
      -> gate command includes:
      `-- --summary-json --skip-telegram`;
    - `./scripts/autonomous_operator_profile.sh --mode dry-run --project n8n-builder-demo-234328 --print-plan --acceptance-preset fast --acceptance-extra-args "--summary-json"`
      -> preview command includes:
      `-- --summary-json`.

214. `P1` Operator `--no-remediation` Alias
- Status: `done`
- Scope:
  - добавить UX-алиас `--no-remediation` как синоним `--no-remediate`;
  - сохранить совместимость существующего поведения и precedence правил;
  - зафиксировать в docs/operator cheatsheet.
- Done when:
  - `autonomous_operator_profile.sh` принимает `--no-remediation`;
  - alias отключает remediation для daily/deep так же, как `--no-remediate`;
  - документация отражает alias.
- Progress:
  - `scripts/autonomous_operator_profile.sh`:
    - parser обновлен:
      - `--no-remediate|--no-remediation` -> `REMEDIATE_OVERRIDE=false`;
    - usage/examples обновлены с alias.
  - `scripts/tests/test_autonomous_operator_profile_script.py`:
    - добавлен поведенческий test:
      - `test_operator_profile_cli_no_remediation_alias_sets_effective_flags_false`.
  - docs sync:
    - `docs/LOCAL_PROD_RUNBOOK.md` (CLI overrides section);
    - `docs/ops/acceptance-automation-map.md` (entrypoint flags list).
- Validation (April 14, 2026):
  - unit:
    - `uv run pytest scripts/tests/test_autonomous_operator_profile_script.py -q`
      -> `20 passed`;
  - docs guardrails:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_docs_navigation.py` -> `pass`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_acceptance_runbook_sanity_sync.py` -> `pass`;
 - print-plan alias check:
    - `./scripts/autonomous_operator_profile.sh --mode daily --project n8n-builder-demo-234328 --print-plan --no-remediation`
      -> `daily_auto_remediate_stale=false` and remediation step is skipped.

215. `P1` Session Data Reveal Hint for Container Runtime
- Status: `done`
- Scope:
  - убрать технический noise в fallback `Data` flow при запуске Hive в Docker;
  - вернуть оператору явный `hint` (использовать `Export`) при отсутствии launcher (`xdg-open/open/explorer`);
  - улучшить UX-сообщение в Web UI (path + hint + confirmation копирования пути).
- Done when:
  - `POST /api/sessions/{id}/reveal` при `FileNotFoundError` возвращает structured fallback c `hint`;
  - кнопка `Data` в Web UI показывает человеко-понятный fallback с `hint`;
  - regression tests покрывают missing-launcher path.
- Progress:
  - `core/framework/server/routes_sessions.py`:
    - `handle_reveal_session_folder` расширен специальной веткой:
      - `except FileNotFoundError` -> `{opened:false, path, launcher, error, hint}`;
    - error normalized to operator-readable text:
      - `Launcher '<name>' is unavailable in this environment`;
      - `hint: Use Export to download the session archive (.zip).`
  - `core/framework/server/tests/test_api.py`:
    - добавлен test:
      - `test_reveal_session_folder_returns_container_hint_when_launcher_missing`.
  - `core/frontend/src/api/sessions.ts`:
    - тип `revealFolder` дополнен полем `hint?: string`.
  - `core/frontend/src/pages/workspace.tsx`:
    - `Data` fallback alert обновлен:
      - показывает `hint`, если пришел от backend;
      - best-effort копирует `path` в clipboard и добавляет строку подтверждения.
- Validation (April 14, 2026):
  - backend tests:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -k "reveal_session_folder" -q`
      -> `3 passed`;
 - container-first frontend build:
    - `docker run --rm -v "$PWD":/work -w /work/core/frontend node:22-bookworm bash -lc 'npm ci --no-audit --no-fund >/tmp/npm-ci.log && npm run build'`
      -> `pass` (`vite build` success).

216. `P2` Agent Catalog vs Session History UX Clarification
- Status: `done`
- Scope:
  - убрать операторскую путаницу из-за разных счетчиков на `My Agents` и в левом sidebar;
  - явно обозначить, что sidebar показывает сессии, а `My Agents` показывает каталог агентов.
- Done when:
  - header в sidebar явно говорит `Session History`;
  - в `My Agents` добавлена подсказка о source-of-truth (`exports/` catalog vs session history).
- Progress:
  - `core/frontend/src/components/HistorySidebar.tsx`:
    - header label изменен с `History` на `Session History`.
  - `core/frontend/src/pages/my-agents.tsx`:
    - под counters добавлена строка:
      `Agent catalog (from exports/) — separate from Session History counts.`
 - Validation (April 14, 2026):
  - container-first frontend build:
    - `docker run --rm -v "$PWD":/work -w /work/core/frontend node:22-bookworm bash -lc 'npm ci --no-audit --no-fund >/tmp/npm-ci.log && npm run build'`
      -> `pass` (`vite build` success).

217. `P1` Queen Startup Tool-Noise Suppression (No-Worker Sessions)
- Status: `done`
- Scope:
  - убрать ложный warning на старте queen в сессиях без загруженного worker;
  - сохранить warning только для реально неожиданных missing tools.
- Done when:
  - в planning/queen-only session больше нет warning:
    `Queen: tools not available: ['get_worker_health_summary']`;
  - при этом фильтрация не скрывает другие missing tools.
- Progress:
  - `core/framework/server/queen_orchestrator.py`:
    - в этапе подготовки `available_tools` добавлен expected-missing filter:
      - когда `session.graph_runtime` отсутствует, `get_worker_health_summary` исключается из warning-set;
    - `node_updates["tools"]` продолжает формироваться из реально зарегистрированных tools.
- Validation (April 14, 2026):
  - unit:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_queen_orchestrator.py -q`
      -> `3 passed`;
 - container-first runtime smoke:
    - `docker compose up -d --build hive-core` -> `pass`;
    - `curl -sS http://localhost:8787/api/health` -> `status=ok`;
    - create queen-only project session:
      `POST /api/sessions {"project_id":"n8n-builder-demo-234328","initial_prompt":"smoke"}` -> `201`;
    - `docker compose logs --tail=120 hive-core | rg "tools not available|get_worker_health_summary"`:
      no startup warning for that session.

218. `P1` Session Create API Hint for Unknown Project IDs
- Status: `done`
- Scope:
  - улучшить операторский UX при `POST /api/sessions` с несуществующим `project_id`;
  - вернуть actionable payload вместо голого `error` текста.
- Done when:
  - при `Project '<id>' not found` API возвращает:
    - `hint`,
    - `default_project_id`,
    - `available_project_ids`.
- Progress:
  - `core/framework/server/routes_sessions.py`:
    - в обработке `ValueError` добавлен project-not-found branch
      с расширенным `409` JSON payload.
  - `core/framework/server/tests/test_api.py`:
    - добавлен test:
      - `test_create_session_project_not_found_returns_project_hint`.
- Validation (April 14, 2026):
  - backend tests:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -k "create_session_project_not_found_returns_project_hint" -q`
      -> `1 passed`;
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -k "reveal_session_folder or create_session_project_not_found_returns_project_hint" -q`
      -> `4 passed`;
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_queen_orchestrator.py -q`
      -> `3 passed`.
 - container runtime check:
    - `docker compose up -d --build hive-core` -> `pass`;
    - `POST /api/sessions {"project_id":"default","initial_prompt":"smoke"}` now returns:
      `{error,hint,default_project_id,available_project_ids}`.

219. `P1` Recall Selector Robust JSON Extraction (Startup Noise Fix)
- Status: `done`
- Scope:
  - устранить production-noise в логах queen startup:
    `recall: memory selection failed (Expecting value...)`;
  - повысить устойчивость recall selector к fenced/wrapped JSON ответам от LLM.
- Done when:
  - recall selector парсит:
    - strict JSON object;
    - markdown fenced JSON;
    - JSON payload, обёрнутый служебным текстом;
  - в типовой новой сессии warning `memory selection failed` не появляется.
- Progress:
  - `core/framework/agents/queen/recall_selector.py`:
    - добавлен helper `_extract_json_payload(raw)`:
      - strict `json.loads`;
      - fenced block extraction (` ```json ... ``` `);
      - fallback extraction первого JSON-like объекта/массива из текста;
    - `select_memories(...)` переведен на robust parser;
    - поддержана форма payload как `list` и как `dict["selected_memories"]`.
  - `core/tests/test_queen_memory.py`:
    - добавлены tests:
      - `test_select_memories_accepts_markdown_fenced_json`;
      - `test_select_memories_accepts_wrapped_json_payload`.
- Validation (April 15, 2026):
  - unit:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/tests/test_queen_memory.py -k "select_memories" -q`
      -> `5 passed`;
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_queen_orchestrator.py -q`
      -> `3 passed`.
 - container runtime smoke:
    - `docker compose up -d --build hive-core` -> `pass`;
    - create new session in project `n8n-builder-demo-234328`;
    - `docker compose logs --tail=220 hive-core | rg "memory selection failed|recall: ..."`:
      no startup warning for the smoke session.

220. `P1` MCP Zero-Tool Log Clarification (first-wins dedupe)
- Status: `done`
- Scope:
  - убрать двусмысленный runtime-signal при загрузке `files-tools`, когда все tool names уже заняты более ранними MCP servers;
  - явно различать “реальная ошибка” и “0 new tools из-за first-wins dedupe”.
- Done when:
  - в логах `hive-core` для `allow_zero_tools` нет misleading формулировки;
  - есть один понятный info-сигнал с причиной (`all discovered tools were already present`).
- Progress:
  - `core/framework/runner/tool_registry.py`:
    - `register_mcp_server(...)` улучшен:
      - добавлен подсчет `tools_discovered`, `tools_skipped_existing`, `tools_skipped_cap`;
      - при `count==0` и полном overlap с ранее загруженными tools:
        логирует явное first-wins сообщение:
        `registered 0 new tools; all N discovered tools were already present in registry`;
    - `_register_mcp_server_with_retry(...)`:
      - убран дублирующий `allow_zero_tools` лог, чтобы не было двойных строк при штатном dedupe.
- Validation (April 15, 2026):
  - targeted unit:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/tests/test_tool_registry.py -k "load_registry_servers" -q`
      -> `3 passed`;
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_queen_orchestrator.py -q`
      -> `3 passed`.
 - container runtime smoke:
    - `docker compose up -d --build hive-core` -> `pass`;
    - new session start in project `n8n-builder-demo-234328`;
    - `docker compose logs --tail=260 hive-core | rg "files-tools|registered 0 new tools|all .* discovered tools"`:
      observed single informative line:
      `MCP server 'files-tools' registered 0 new tools; all 6 discovered tools were already present in registry (first-wins)`.

221. `P1` Tool Registry Test Stability (Built-in Tool Baseline)
- Status: `done`
- Scope:
  - устранить flaky/false-negative в unit test для `ToolRegistry.get_registered_names`;
  - адаптировать тест к текущему контракту registry (built-in framework tools могут присутствовать по умолчанию).
- Done when:
  - тест не требует exact equality c пользовательскими test-tools;
  - full `core/tests/test_tool_registry.py` проходит стабильно.
- Progress:
  - `core/tests/test_tool_registry.py`:
    - `test_get_registered_names_lists_all_tools` обновлен:
      - вместо `== {"alpha","beta","gamma"}` теперь проверяется `issubset(...)`;
      - добавлен комментарий про built-in tools baseline.
 - Validation (April 15, 2026):
  - `./scripts/hive_ops_run.sh uv run --package framework pytest core/tests/test_tool_registry.py -q`
    -> `33 passed`;
  - regression companion:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_queen_orchestrator.py -q`
      -> `3 passed`.

223. `P1` Server API Test Regression Fix (Default Project Override)
- Status: `done`
- Scope:
  - устранить регрессию в `core/framework/server/tests/test_api.py`, проявлявшуюся при non-`default`
    `HIVE_DEFAULT_PROJECT_ID`;
  - стабилизировать trigger/policy tests для project-scoped execution queue.
- Done when:
  - tests не зависят от literal project id `default`;
  - полный `test_api.py` снова зеленый.
- Progress:
  - `core/framework/server/tests/test_api.py`:
    - trigger-related tests переведены на runtime project id:
      - `project_id = app[APP_KEY_MANAGER].default_project_id()`;
      - `session.project_id`, `update_project(...)`, queue URL assertions используют этот `project_id`.
    - updated tests:
      - `test_trigger_rejects_when_project_limit_reached`;
      - `test_trigger_queues_when_project_limit_reached`;
      - `test_trigger_respects_project_specific_limit`;
      - `test_trigger_blocked_by_project_policy`.
- Validation (April 15, 2026):
  - targeted:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -k "trigger_queues_when_project_limit_reached or trigger_respects_project_specific_limit or trigger_blocked_by_project_policy or trigger_rejects_when_project_limit_reached" -q`
      -> `4 passed`;
 - full module:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -q`
      -> `174 passed` (deprecation warning resolved by item `224`).

224. `P1` aiohttp Middleware Deprecation Cleanup (HTTPException Return)
- Status: `done`
- Scope:
  - убрать deprecation warning:
    `returning HTTPException object is deprecated (#2415)`;
  - сохранить текущий CORS behavior для error-paths.
- Done when:
  - `cors_middleware` больше не возвращает `web.HTTPException` как response object;
  - `test_api.py` проходит без warning summary от этого кейса.
- Progress:
  - `core/framework/server/app.py`:
    - в `cors_middleware` ветка `except web.HTTPException as exc` заменена:
      - раньше: `response = exc`;
      - теперь: `response = web.Response(status=exc.status, reason=exc.reason, text=exc.text, headers=exc.headers)`.
- Validation (April 15, 2026):
  - targeted:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -k "worker_input_route_removed" -q`
      -> `1 passed`;
  - full module:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -q`
      -> `174 passed` (warning no longer present).

222. `P1` API Regression Test Portability (Project ID Baseline)
- Status: `done`
- Scope:
  - historical duplicate of item `223` (kept for audit trail);
  - устранить environment-coupled падения в `core/framework/server/tests/test_api.py`,
    где проект был захардкожен как `default`;
  - сделать тесты независимыми от `HIVE_DEFAULT_PROJECT_ID` override.
- Done when:
  - trigger-related tests используют runtime `manager.default_project_id()` вместо literal `default`;
  - полный `test_api.py` проходит в текущем окружении.
- Progress:
  - `core/framework/server/tests/test_api.py`:
    - обновлены tests:
      - `test_trigger_rejects_when_project_limit_reached`;
      - `test_trigger_queues_when_project_limit_reached`;
      - `test_trigger_respects_project_specific_limit`;
      - `test_trigger_blocked_by_project_policy`;
    - изменения:
      - `project_id = app[APP_KEY_MANAGER].default_project_id()`;
      - `session.project_id` и `update_project(...)` привязаны к `project_id`;
      - queue endpoint assert использует `f"/api/projects/{project_id}/queue"`.
- Validation (April 15, 2026):
  - targeted:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -k "trigger_queues_when_project_limit_reached or trigger_respects_project_specific_limit or trigger_blocked_by_project_policy or trigger_rejects_when_project_limit_reached" -q`
      -> `4 passed`;
  - full module:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -q`
      -> `174 passed` (warning resolved in item `224`).

225. `P1` Telegram Sign-off Artifact Consistency (Manual Checklist Sync)
- Status: `done`
- Scope:
  - устранить рассинхрон в `docs/ops/telegram-signoff/latest.md`, где `manual_status=pass`,
    но checklist items оставались unchecked;
  - зафиксировать re-validation timestamp после повторного smoke-прогона.
- Done when:
  - checklist пункты в `latest.md` проставлены как completed;
  - notes отражают актуальную дату повторной валидации.
- Progress:
  - `docs/ops/telegram-signoff/latest.md`:
    - обновлен `generated_at` на `2026-04-15T15:05:00Z`;
    - manual checklist sync: все 4 пункта переведены в `[x]`;
    - notes дополнены явной пометкой `re-validated on 2026-04-15`.
- Validation (April 15, 2026):
  - manual review:
    - `manual_status=pass` согласован с checklist `[x]` и notes;
  - status tooling:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status.py --path docs/autonomous-factory/12-backlog-task-list.md`
      -> `tasks_total=225`, `done=225`, `todo=0`.

226. `P1` Container Quality Gate Re-Run (Post-Rebuild Stability)
- Status: `done`
- Scope:
  - выполнить container-first quality gate после `docker compose up -d --build hive-core`;
  - зафиксировать runtime health и базовый Telegram bridge test pass.
- Done when:
  - `hive-core` пересобран и поднят без runtime ошибок;
  - `/api/health` возвращает `status=ok` и `telegram_bridge.running=true`;
  - ключевой bridge test suite проходит.
- Progress:
  - выполнен `docker compose up -d --build hive-core` (image `hive-hive-core` пересобран, контейнер recreated);
  - `curl http://localhost:8787/api/health | jq .` -> `status=ok`, bridge `running=true`;
  - `docker compose logs --tail=140 hive-core | rg "ERROR|Traceback|Exception|failed" -i` -> no matches;
  - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q`
    -> `28 passed`.
- Validation (April 15, 2026):
  - container runtime: healthy;
  - bridge/server smoke tests: pass.

227. `P0` Autonomous Ops Health Recovery (Stale Run Remediation)
- Status: `done`
- Scope:
  - восстановить `autonomous_ops_health_check` после обнаружения массовых stale runs;
  - выполнить безопасную remediation-процедуру (`dry-run` -> `apply`) без удаления истории.
- Done when:
  - `stuck_runs_total` и `no_progress_projects_total` возвращаются к `0`;
  - `./scripts/autonomous_ops_health_check.sh` проходит успешно.
- Progress:
  - baseline before fix:
    - `./scripts/autonomous_ops_health_check.sh` -> fail:
      `stuck_runs_total=168`, `no_progress_projects_total=162`;
  - dry-run remediation:
    - `HIVE_AUTONOMOUS_REMEDIATE_MAX_RUNS=500 HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=true HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=false ./scripts/autonomous_remediate_stale_runs.sh`
      -> `candidates_total=168`, `selected_total=168`;
  - apply remediation:
    - `HIVE_AUTONOMOUS_REMEDIATE_MAX_RUNS=500 HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=false HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=true HIVE_AUTONOMOUS_REMEDIATE_REASON=ops_health_recovery ./scripts/autonomous_remediate_stale_runs.sh`
      -> `remediated_total=168` (`action=escalated`);
  - after fix:
    - `./scripts/autonomous_ops_health_check.sh` -> pass;
    - ops status: `stuck_runs_total=0`, `no_progress_projects_total=0`.
- Validation (April 16, 2026):
  - `./scripts/autonomous_ops_health_check.sh`
    -> `ok: autonomous ops health check passed`;
  - `curl -sS 'http://localhost:8787/api/autonomous/ops/status?include_runs=true' | jq ...`
    confirms all stale-run alerts cleared.
- Re-validation (April 17, 2026):
  - текущий ops baseline снова показал stale активные run'ы:
    - `curl -sS 'http://localhost:8787/api/autonomous/ops/status' | jq ...`
      -> `stuck_runs_total=47`, `runs_by_status.queued=42`, `runs_by_status.in_progress=5`;
  - выполнен controlled remediation replay:
    - dry-run:
      - `HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=true HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=false HIVE_AUTONOMOUS_REMEDIATE_OLDER_THAN_SECONDS=1800 HIVE_AUTONOMOUS_REMEDIATE_MAX_RUNS=200 HIVE_AUTONOMOUS_REMEDIATE_ACTION=escalated HIVE_AUTONOMOUS_REMEDIATE_REASON=ops_housekeeping_apr17 ./scripts/autonomous_remediate_stale_runs.sh`
      -> `candidates_total=47`, `selected_total=47`;
    - apply:
      - `HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=false HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=true HIVE_AUTONOMOUS_REMEDIATE_OLDER_THAN_SECONDS=1800 HIVE_AUTONOMOUS_REMEDIATE_MAX_RUNS=200 HIVE_AUTONOMOUS_REMEDIATE_ACTION=escalated HIVE_AUTONOMOUS_REMEDIATE_REASON=ops_housekeeping_apr17 ./scripts/autonomous_remediate_stale_runs.sh`
      -> `remediated_total=47`;
  - post-check:
    - `curl -sS 'http://localhost:8787/api/autonomous/ops/status' | jq ...`
      -> `stuck_runs_total=0`, no active `queued|in_progress`;
    - `./scripts/autonomous_ops_health_check.sh`
      -> `ok: autonomous ops health check passed`.

228. `P1` Acceptance Ops Summary Container-Mode Scheduler Signal
- Status: `done`
- Scope:
  - убрать двусмысленный `None` в `scheduler_hive_scheduler_container`, когда `docker` CLI
    недоступен (container-first execution via `hive_ops_run.sh`);
  - добавить явный machine-readable статус для этого режима.
- Done when:
  - `scripts/acceptance_ops_summary.py` возвращает `unknown-cli-unavailable` вместо `None`;
  - добавлен unit-test на этот кейс.
- Progress:
  - `scripts/acceptance_ops_summary.py`:
    - `_docker_scheduler_status()`:
      - `except` -> `unknown-cli-unavailable`;
      - `returncode != 0` -> `unknown-compose-error`;
      - stdout non-empty -> `running`, empty -> `not-running`.
  - `scripts/tests/test_acceptance_ops_summary.py`:
    - добавлен `test_docker_scheduler_status_reports_cli_unavailable`.
- Validation (April 16, 2026):
  - targeted unit:
    - `./scripts/hive_ops_run.sh uv run pytest scripts/tests/test_acceptance_ops_summary.py -q`
      -> `5 passed`;
  - regression gate:
    - `./scripts/acceptance_toolchain_self_check.sh`
      -> `Self-check summary: ok=20 failed=0`.

229. `P1` Ops Drill Default Project Resolution (Container-First Robustness)
- Status: `done`
- Scope:
  - устранить падение `scripts/autonomous_ops_drill.sh`, когда `HIVE_AUTONOMOUS_DRILL_PROJECT_IDS=default`,
    но в runtime фактический default project id не равен literal `default`;
  - сохранить совместимость с multi-project CSV input.
- Done when:
  - drill не падает на шаге loop smoke из-за `Project 'default' not found`;
  - при необходимости `default` автоматически резолвится в актуальный `default_project_id` из API.
- Progress:
  - `scripts/autonomous_ops_drill.sh`:
    - добавлены `BASE_URL/API_BASE`;
    - добавлен `resolve_default_project_id()` (`/api/projects` -> `default_project_id` fallback на первый проект);
    - добавлен `replace_default_token()` для CSV `project_ids`;
    - loop smoke использует `RESOLVED_DRILL_PROJECT_IDS` вместо raw input;
    - добавлен явный log `resolved_drill_project_ids=...`.
  - baseline before fix:
    - `./scripts/autonomous_ops_drill.sh` -> fail:
      `Project 'default' not found`.
- Validation (April 16, 2026):
  - syntax:
    - `bash -n scripts/autonomous_ops_drill.sh` -> pass;
  - live drill:
    - `./scripts/autonomous_ops_drill.sh` ->
      `resolved_drill_project_ids=n8n-builder-demo-234328 (default -> n8n-builder-demo-234328)`,
      `Drill summary: ok=5 failed=0`.

230. `P1` Loop-Stale Signal Hardening (Terminal Snapshot Noise Suppression)
- Status: `done`
- Scope:
  - убрать false-positive `loop_stale=true`, когда loop state snapshot terminal (`ok|failed|stopped|idle`)
    и у pipeline нет активных симптомов деградации (`stuck_runs/no_progress`);
  - сохранить strict сигнализацию для реально stale running-loop кейсов.
- Done when:
  - `ops/status` не поднимает `loop_stale` на историческом terminal snapshot без симптомов;
  - stale running loop по-прежнему даёт `loop_stale=true`;
  - API tests на новый контракт проходят.
- Progress:
  - `core/framework/server/routes_autonomous.py`:
    - `loop_stale` теперь подавляется для terminal loop state только если одновременно:
      - `stuck_runs_total == 0`;
      - `no_progress_projects_total == 0`;
    - для running-loop stale поведение без изменений.
  - `core/framework/server/tests/test_api.py`:
    - обновлён stale-loop test на `status=running`;
    - добавлен test на suppression terminal snapshot без active runs;
    - добавлен test на suppression terminal snapshot при healthy active runs.
  - live rollout:
    - hot-sync `routes_autonomous.py` в `hive-core` + restart контейнера;
    - после post-restart remediation stale runs:
      - `HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=false HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=true HIVE_AUTONOMOUS_REMEDIATE_OLDER_THAN_SECONDS=1800 HIVE_AUTONOMOUS_REMEDIATE_MAX_RUNS=200 HIVE_AUTONOMOUS_REMEDIATE_ACTION=escalated ...`
      - итог `stuck_runs_total=0`, `no_progress_projects_total=0`, `loop_stale=false`.
  - устранена инфраструктурная причина расхождения loop heartbeat между контейнерами:
    - `docker-compose.yml` (`hive-scheduler`):
      - `HIVE_SCHEDULER_STATE_PATH` переведен на shared путь
        `/home/hiveuser/.hive/server/autonomous_loop_state.json`;
      - добавлен volume mount: `hive-home:/home/hiveuser/.hive`;
    - `scripts/autonomous_scheduler_daemon.py`:
      - `_write_state()` теперь создаёт parent dir (`mkdir -p`) перед записью state.
    - после recreate `hive-scheduler` loop state стал live-heartbeat (`status=running`, `updated_at` обновляется каждые ~5s).
- Validation (April 17, 2026):
  - targeted API tests:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -k "autonomous_ops_status_reports_stale_loop_state or ignores_stale_terminal_loop_snapshot_without_active_runs or ignores_stale_terminal_loop_snapshot_with_healthy_active_runs or autonomous_ops_status_reads_loop_state_file" -q`
      -> `4 passed`;
  - regression subset:
    - `./scripts/hive_ops_run.sh uv run --package framework pytest core/framework/server/tests/test_api.py -k "autonomous_ops_remediate_stale or autonomous_ops_status" -q`
      -> `16 passed`;
  - live ops:
    - `./scripts/autonomous_ops_health_check.sh`
      -> `ok: autonomous ops health check passed`.
  - scheduler/container runtime:
    - `docker exec hive-scheduler env | grep HIVE_SCHEDULER_STATE_PATH`
      -> `/home/hiveuser/.hive/server/autonomous_loop_state.json`;
    - `curl -sS 'http://localhost:8787/api/autonomous/ops/status' | jq ...`
      -> `loop_stale=false`, `loop.state.status=running`, `loop_stale_seconds~1s`.
  - container-first bake-in:
    - `docker compose up -d --build hive-core hive-scheduler` -> images rebuilt, containers recreated;
    - post-build no-progress cleanup:
      - `HIVE_AUTONOMOUS_REMEDIATE_OLDER_THAN_SECONDS=900 ... ./scripts/autonomous_remediate_stale_runs.sh`
      - `remediated_total=4`;
    - final health:
      - `./scripts/autonomous_ops_health_check.sh`
      -> `ok: autonomous ops health check passed` (`stuck_runs=0`, `no_progress_projects=0`, `loop_stale=false`).
  - strict operator gate re-run (April 17, 2026):
    - global strict health:
      - `HIVE_AUTONOMOUS_HEALTH_PROFILE=prod ./scripts/autonomous_ops_health_check.sh`
      -> `ok` (`stuck_runs=0`, `no_progress_projects=0`, `loop_stale=false`);
    - project operator profile:
      - `./scripts/autonomous_operator_profile.sh --mode daily --project n8n-builder-demo-234328 --project-health-profile strict`
      -> completed successfully:
        - acceptance strict preset: `ok=13 failed=0`;
        - project ops: `stuck_runs_total=0`, `no_progress_projects_total=0`;
        - digest/regression guard: pass.
  - deep operator gate re-run (April 17, 2026):
    - `./scripts/autonomous_operator_profile.sh --mode deep --project n8n-builder-demo-234328 --project-health-profile strict`
      -> completed successfully:
        - deep self-check: `Self-check summary: ok=21 failed=0`;
        - acceptance full-deep preset: `ok=17 failed=0`;
        - acceptance unit bundle: `64 passed`;
        - delivery e2e smoke: `scenarios_ok=2`, `scenarios_failed=0`;
        - project ops: `stuck_runs_total=0`, `no_progress_projects_total=0`, `loop_stale=false`.

231. `P1` Container-First Access Stack Verification + Master Plan DoD Re-Run
- Status: `done`
- Scope:
  - устранить ложные `WARN` в `verify_access_stack.sh` при container-first запуске через
    `hive_ops_run.sh` (docker CLI недоступен внутри runtime);
  - перепроверить master-plan DoD gates единым финальным прогоном (self-check, ops health,
    MCP health, delivery smoke, backup/restore dry-run, backlog sync).
- Done when:
  - `verify_access_stack.sh` показывает корректные `OK` в host-mode и container-mode;
  - финальные DoD проверки проходят без блокирующих ошибок.
- Progress:
  - `scripts/verify_access_stack.sh`:
    - добавлен runtime-aware dual-mode:
      - `docker` mode: использует `docker compose exec/inspect` (как раньше);
      - `container` mode: локальные socket probes для `REDIS_URL`/`DATABASE_URL`,
        local refresher-state probe, и `OK`-skip для container inspect check;
    - добавлены helper-функции:
      - `docker_mode_available`;
      - `run_socket_probe`;
      - `run_google_refresh_state_probe`.
  - до фикса:
    - `./scripts/hive_ops_run.sh ./scripts/verify_access_stack.sh`
      -> ложные `WARN` по `Redis/Postgres/google-token-refresher`.
  - после фикса:
    - host-mode:
      - `./scripts/verify_access_stack.sh` -> все target checks `OK`;
    - container-first:
      - `./scripts/hive_ops_run.sh ./scripts/verify_access_stack.sh`
        -> `Redis/Postgres` = `OK`, refresher container inspect = `OK skip`,
           refresher state = `OK`.
  - `scripts/autonomous_delivery_e2e_smoke.py`:
    - добавлен auto-resolve default `base_url`:
      - `HIVE_DELIVERY_E2E_BASE_URL` -> `HIVE_BASE_URL` -> runtime probe
        (`localhost:8787` then `hive-core:8787`);
    - устранён container-first fail `Connection refused` при запуске через
      `hive_ops_run.sh` без явного `--base-url`.
  - `scripts/tests/test_autonomous_delivery_e2e_smoke.py`:
    - добавлены unit tests на default base URL resolution:
      - explicit env priority;
      - shared `HIVE_BASE_URL` fallback;
      - `hive-core` autodetect when localhost is unreachable.
- Validation (April 17, 2026):
  - syntax:
    - `bash -n scripts/verify_access_stack.sh` -> pass;
  - backlog governance:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status.py --path docs/autonomous-factory/12-backlog-task-list.md`
      -> `tasks_total=230`, `done=230`, `todo=0`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/validate_backlog_markdown.py`
      -> `[ok] backlog validation passed`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_consistency.py`
      -> in sync.
  - acceptance + ops:
    - `./scripts/acceptance_toolchain_self_check.sh`
      -> `Self-check summary: ok=20 failed=0`;
    - `HIVE_AUTONOMOUS_HEALTH_PROFILE=prod ./scripts/autonomous_ops_health_check.sh`
      -> `ok` (`stuck_runs=0`, `no_progress_projects=0`, `loop_stale=false`);
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/mcp_health_summary.py --since-minutes 30`
      -> `status: ok`, `ok: 5/5`.
  - delivery + recovery:
    - `./scripts/hive_ops_run.sh uv run pytest scripts/tests/test_autonomous_delivery_e2e_smoke.py -q`
      -> `22 passed`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py --base-url http://hive-core:8787`
      -> `status: ok`, `scenarios_ok=2`, `scenarios_failed=0`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py`
      -> `status: ok`, auto-selected `base_url=http://hive-core:8787`;
    - `./scripts/backup_hive_state.sh`
      -> backup artifact created;
    - `./scripts/restore_hive_state.sh --archive <latest> --dry-run`
      -> restore plan rendered, no changes applied;
    - `./scripts/local_prod_checklist.sh`
      -> checklist complete (`OK`).
  - backlog post-update re-check:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status.py --path docs/autonomous-factory/12-backlog-task-list.md`
      -> `tasks_total=231`, `done=231`, `todo=0`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/validate_backlog_markdown.py`
      -> `tasks_total=231`, `in_progress=[]`, `focus_refs=[]`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_backlog_status_consistency.py`
      -> task id/status/focus sets in sync.

232. `P0` Upstream Migration Wave 3 - Freeze and Evidence Baseline
- Status: `done`
- Scope:
  - зафиксировать точный baseline перед миграцией (`rev delta`, `name-status`, overlap, DoD gates);
  - подтвердить стартовую работоспособность локальной фабрики до начала интеграции upstream.
- Done when:
  - baseline документы и метрики обновлены;
  - pre-migration operational gates (`checklist/self-check/ops-health`) сохранены как evidence.
- Progress:
  - подготовлен migration plan:
    - `docs/autonomous-factory/21-upstream-migration-wave3-plan.md`;
  - подготовлен baseline snapshot:
    - `docs/ops/upstream-migration/baseline-2026-04-17.md`;
    - `docs/ops/upstream-migration/latest.md`;
  - зафиксированы стартовые метрики:
    - `main...origin/main` -> `0 ahead / 225 behind`;
    - upstream delta entries -> `649`;
    - overlap (`local ∩ upstream`) -> `68`.
  - migration gates re-validated (April 18, 2026):
    - `./scripts/acceptance_toolchain_self_check.sh` -> `Self-check summary: ok=20 failed=0`;
    - `HIVE_AUTONOMOUS_HEALTH_PROFILE=prod ./scripts/autonomous_ops_health_check.sh` -> `ok`;
    - `./scripts/local_prod_checklist.sh` -> `Checklist complete`.
  - operational remediation before final prod health gate:
    - `./scripts/autonomous_remediate_stale_runs.sh` (dry-run) found `run_7044c40bd3` stale in project `n8n-builder-demo-234328`;
    - remediation applied with `HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=false HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=true ./scripts/autonomous_remediate_stale_runs.sh` (`remediated_total=1`).

233. `P0` Upstream Wave 3 - Unclassified Decision Registry Refresh
- Status: `done`
- Scope:
  - обновить triage coverage для текущего upstream delta (`other_unclassified`);
  - привести `docs/ops/upstream-unclassified-decisions.json` и markdown report в консистентное состояние.
- Progress:
  - выполнен стартовый health-check decisions coverage:
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_unclassified_delta_decisions.py`
      -> `missing decisions for 619 path(s)`;
  - подтверждён объём работ по refresh decision registry для текущего upstream delta wave.
  - decision registry refreshed for full wave coverage:
    - `docs/ops/upstream-unclassified-decisions.json` expanded to cover current `other_unclassified` set;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/check_unclassified_delta_decisions.py`
      -> `[ok] covered_unclassified=634`, `stale_decisions=0`;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/render_unclassified_decision_report.py --write docs/ops/upstream-unclassified-decisions.md`
      -> report regenerated;
    - `./scripts/hive_ops_run.sh uv run --no-project python scripts/render_unclassified_decision_report.py --check docs/ops/upstream-unclassified-decisions.md`
      -> report sync confirmed.
- Done when:
  - `scripts/check_unclassified_delta_decisions.py` проходит без missing decisions;
  - decisions register покрывает весь unclassified набор текущей волны.

234. `P0` Upstream Wave 3 - Clean Landing Branch Bootstrap
- Status: `done`
- Scope:
  - подготовить clean migration branch от `origin/main` (без merge в текущий dirty workspace);
  - зафиксировать рабочую схему переноса локальных factory модулей в upstream-first базу.
- Progress:
  - добавлен bootstrap script:
    - `scripts/upstream_landing_branch_bootstrap.sh` (`--print-only` default, `--apply` for clean checkout);
  - добавлен probe script для clean checkout evidence без branch switch текущего workspace:
    - `scripts/upstream_landing_branch_probe.sh`;
  - добавлена runbook-документация:
    - `docs/ops/upstream-migration/landing-branch-bootstrap.md`;
  - зафиксирован latest bootstrap snapshot:
    - `docs/ops/upstream-migration/landing-branch-bootstrap-latest.md`
      (ahead/behind, dirty overlap, replay domains, apply command);
  - создан local landing ref без checkout рабочей ветки:
    - `migration/upstream-wave3` tracking `origin/main`;
  - зафиксирован clean landing probe snapshot:
    - `docs/ops/upstream-migration/landing-branch-probe-latest.md`
      (`probe worktree dirty paths=0`);
  - `./scripts/upstream_landing_branch_bootstrap.sh --print-only` выполнен, branch switch не выполнялся.
- Done when:
  - есть clean landing branch с подтвержденным baseline boot;
  - задокументирован список replay domains и порядок применения.

235. `P1` Upstream Wave 3 - Replay of Project/Autonomous/Telegram Control Plane
- Status: `done`
- Scope:
  - перенести и адаптировать локальные factory-модули:
    - `routes_projects`, `routes_autonomous`, `project_*`, `telegram_bridge`, `autonomous_pipeline`;
  - обеспечить API/contract parity с новым upstream runtime.
- Progress:
  - собран deterministic replay bundle для control-plane модулей:
    - script: `scripts/upstream_replay_bundle.sh`;
    - manifest: `docs/ops/upstream-migration/replay-bundle-wave3-latest.md`;
    - artifact: `docs/ops/upstream-migration/replay-bundles/wave3-20260417-213932.tar.gz`
      (included paths=`36`, missing=`0`);
  - добавлен compatibility classification на target `origin/main`:
    - script: `scripts/upstream_replay_compat_report.sh`;
    - report: `docs/ops/upstream-migration/replay-bundle-wave3-compat-latest.md`
      (`add=36`, `overlay=0`);
  - выполнен apply probe в изолированном clean clone:
    - script: `scripts/upstream_replay_apply_probe.sh`;
    - report: `docs/ops/upstream-migration/replay-apply-probe-latest.md`
      (`changed=36`, `modified/tracked=0`, `untracked=36`);
  - Batch A dependency unblocked via landing integration:
    - landing integration evidence recorded in
      `docs/ops/upstream-migration/overlap-batch-a-landing-integration-latest.md`;
    - clean landing clone commit created:
      - `ff9b88b9a51071d4c5c3b2d82346c2bfb807080a` (branch `migration/upstream-wave3`);
    - bundle-based apply path established for replay+dependencies+hotspots.
  - control-plane contract gates on landing clone are green:
    - `test_control_plane_contract` (`TestProjectsAPI or TestAutonomousPipeline`) -> `ok`;
    - `test_telegram_bridge.py` -> `ok`;
    - `test_api` profile subset + `test_queen_orchestrator.py` -> `ok`.
  - добавлен ops guide:
    - `docs/ops/upstream-migration/replay-bundle-wave3.md`.
  - подготовлен post-replay validation runbook:
    - `docs/ops/upstream-migration/replay-validation-wave3.md`
      (API/Telegram tests + container-first ops + delivery smoke + MCP health checks).
- Done when:
  - project-scoped и autonomous endpoints работают на landing branch;
  - Telegram control-center отвечает по ключевым сценариям.

236. `P1` Upstream Wave 3 - Overlap Batch A (Server Hotspots)
- Status: `done`
- Scope:
  - разрешить конфликты server overlap:
    - `app.py`, `session_manager.py`, `routes_execution.py`, `routes_sessions.py`,
      `queen_orchestrator.py`, `routes_credentials.py`, API tests.
- Progress:
  - exported full overlap patch against `origin/main`:
    - `docs/ops/upstream-migration/overlap-batch-a-latest.patch` (~507KB, 11876 lines);
    - `docs/ops/upstream-migration/overlap-batch-a-latest.md` (numstat and file set);
  - identified high-risk signal:
    - full-file overlay is too wide for safe merge, requiring focus-hunk strategy.
  - generated focus artifacts:
    - `docs/ops/upstream-migration/overlap-batch-a-focus-latest.md` (local vs upstream activation hooks map);
    - `docs/ops/upstream-migration/overlap-batch-a-focus-latest.patch`
      (`matched_files=6`, `matched_hunks=43`);
    - `docs/ops/upstream-migration/overlap-batch-a-focus-summary-latest.md`;
  - probe outcomes:
    - `git apply --check` report:
      - `docs/ops/upstream-migration/overlap-batch-a-focus-probe-latest.md`
      - clean apply passes (`changed paths=5`);
    - `git apply --3way --index` report:
      - `docs/ops/upstream-migration/overlap-batch-a-conflict-probe-latest.md`
      - clean apply in 3way mode (`unmerged files=0`);
    - file-by-file apply probe report:
      - `docs/ops/upstream-migration/overlap-batch-a-file-probe-latest.md`
      - all 6 hotspot files pass `git apply --check`;
  - prepared controlled apply step for landing branch:
    - script: `scripts/upstream_overlap_batch_a_apply.sh` (`--check` / `--apply`);
    - branch/worktree guardrails validated (fails outside `migration/upstream-wave3` as expected).
  - added integration dependency-closure probe:
    - script: `scripts/upstream_overlap_batch_a_integration_probe.sh`;
    - report: `docs/ops/upstream-migration/overlap-batch-a-integration-probe-latest.md`;
    - findings:
      - baseline (`replay + focus patch`) fails with
        `ModuleNotFoundError: No module named 'framework.runtime'`;
      - compatibility fix implemented in local tree:
        - `core/framework/runner/__init__.py` lazy exports (no eager `runner.py` import);
      - overlay (`runtime + graph + runner + routes_graphs.py`) now passes both:
        - app smoke (`create_app` + route checks),
        - `pytest core/framework/server/tests/test_api.py -k "health" -q`;
      - next blocker is landing this closure on branch `migration/upstream-wave3`.
  - created deterministic dependency bundle for landing/probe apply:
    - script: `scripts/upstream_overlap_batch_a_dependency_bundle.sh`;
    - manifest: `docs/ops/upstream-migration/overlap-batch-a-dependency-bundle-latest.md`;
    - artifact:
      - `docs/ops/upstream-migration/replay-bundles/wave3-batch-a-dependency-20260418-011208.tar.gz`.
    - dependency scope expanded with runtime prerequisites:
      - `core/framework/model_routing.py`,
      - `core/framework/llm/fallback.py`.
  - added deterministic server hotspots bundle:
    - script: `scripts/upstream_overlap_batch_a_hotspots_bundle.sh`;
    - manifest: `docs/ops/upstream-migration/overlap-batch-a-hotspots-bundle-latest.md`;
    - artifact:
      - `docs/ops/upstream-migration/replay-bundles/wave3-batch-a-hotspots-20260418-011209.tar.gz`.
  - added guarded landing apply helper for bundle path:
    - script: `scripts/upstream_overlap_batch_a_bundle_apply.sh` (`--check` / `--apply`);
    - guardrails: expected branch + clean worktree checks before apply.
  - added landing rehearsal gate runner:
    - script: `scripts/upstream_overlap_batch_a_landing_rehearsal.sh`;
    - report: `docs/ops/upstream-migration/overlap-batch-a-landing-rehearsal-latest.md`;
    - applies replay+dependency+hotspots bundles on clean `origin/main` clone;
    - gate results:
      - `test_api.py` profile subset (`health/session/execution/credentials`): `ok`;
      - `test_telegram_bridge.py`: `ok`;
      - `test_queen_orchestrator.py`: `ok`.
    - remaining step: execute same bundle apply path on real `migration/upstream-wave3`
      landing branch and record commit-level integration evidence.
  - added execution runbook:
    - `docs/ops/upstream-migration/overlap-batch-a.md`.
  - added ordered conflict-resolution queue + checkpoints:
    - `docs/ops/upstream-migration/overlap-batch-a-execution-queue.md`.
  - added deterministic hotspots bundle + guarded bundle apply helper:
    - `scripts/upstream_overlap_batch_a_hotspots_bundle.sh`;
    - `scripts/upstream_overlap_batch_a_bundle_apply.sh`.
  - added landing rehearsal + landing integration evidence:
    - rehearsal report:
      - `docs/ops/upstream-migration/overlap-batch-a-landing-rehearsal-latest.md`;
    - integration report:
      - `docs/ops/upstream-migration/overlap-batch-a-landing-integration-latest.md`;
    - integration commit (clean landing clone):
      - `ff9b88b9a51071d4c5c3b2d82346c2bfb807080a`;
    - gate results (`ok`):
      - `test_api` profile subset (`health/session/execution/credentials`),
      - `test_telegram_bridge.py`,
      - `test_queen_orchestrator.py`,
      - `test_control_plane_contract`.
- Done when:
  - server batch интегрирован без регресса project/session/autonomous semantics;
  - профильные backend тесты проходят.

237. `P1` Upstream Wave 3 - Overlap Batch B (Frontend Operator UX)
- Status: `done`
- Scope:
  - разрешить frontend overlap:
    - `workspace/my-agents/history sidebar/api types` и связанные operator панели.
- Progress:
  - добавлен детерминированный export Batch B:
    - `scripts/upstream_overlap_batch_b_export.sh`;
    - артефакты:
      - `docs/ops/upstream-migration/overlap-batch-b-latest.patch`,
      - `docs/ops/upstream-migration/overlap-batch-b-latest.md` (numstat report).
  - добавлен dependency bundle для operator UX closure:
    - `scripts/upstream_overlap_batch_b_dependency_bundle.sh`;
    - `docs/ops/upstream-migration/overlap-batch-b-dependency-bundle-latest.md`.
  - добавлен frontend bundle + guarded apply helper:
    - `scripts/upstream_overlap_batch_b_bundle.sh`;
    - `scripts/upstream_overlap_batch_b_bundle_apply.sh`.
  - добавлен landing rehearsal:
    - `scripts/upstream_overlap_batch_b_landing_rehearsal.sh`;
    - `docs/ops/upstream-migration/overlap-batch-b-landing-rehearsal-latest.md`.
  - clean-clone rehearsal (`origin/main`) results:
    - required gates `ok`: `npm ci`, `operator TS smoke`, `chat-helpers vitest`.
    - informational `npm run build` остаётся `failed` из-за legacy out-of-scope страниц
      (`queen-dm`, `colony-chat`, legacy credentials/config surface) при изолированном Batch B.
- Done when:
  - web operator UX сохраняет локальные control-center сценарии;
  - сборка фронта и smoke по ключевым экранам проходят.

238. `P1` Upstream Wave 3 - Overlap Batch C (Tools/MCP Compatibility)
- Status: `done`
- Scope:
  - разрешить конфликтные изменения в `tools/*` и MCP layers;
  - сохранить локальные гарантии health-check и credential behavior.
- Progress:
  - добавлен детерминированный overlap export для Batch C:
    - `scripts/upstream_overlap_batch_c_export.sh`;
    - `docs/ops/upstream-migration/overlap-batch-c-latest.patch`;
    - `docs/ops/upstream-migration/overlap-batch-c-latest.md`.
  - добавлены dependency/tools bundles + guarded apply helper:
    - `scripts/upstream_overlap_batch_c_dependency_bundle.sh`;
    - `scripts/upstream_overlap_batch_c_bundle.sh`;
    - `scripts/upstream_overlap_batch_c_bundle_apply.sh`.
  - добавлен landing rehearsal:
    - `scripts/upstream_overlap_batch_c_landing_rehearsal.sh`;
    - `docs/ops/upstream-migration/overlap-batch-c-landing-rehearsal-latest.md`.
  - rehearsal results:
    - clean clone: `python compile overlap files=ok`, `mcp_servers.json parse=ok`;
    - live runtime: `test_coder_tools_server=ok`, `test_github_tool=ok`,
      `mcp_health_summary=ok`, `verify_access_stack=ok`.
- Done when:
  - `mcp_health_summary.py` и `verify_access_stack.sh` проходят;
  - MCP tool registrations работают без silent-fail.

239. `P1` Upstream Wave 3 - Full Regression Gate (Container-First)
- Status: `done`
- Scope:
  - выполнить обязательный regression gate после всех batch merge:
    - `acceptance_toolchain_self_check`,
    - `check_runtime_parity`,
    - `local_prod_checklist`,
    - `test_api/test_telegram_bridge`,
    - `autonomous_delivery_e2e_smoke`.
- Progress:
  - regression gate commands executed in container-first runtime:
    - `./scripts/acceptance_toolchain_self_check.sh` -> `ok` (`self-check summary: ok=20 failed=0`);
    - `./scripts/check_runtime_parity.sh` -> `ok`;
    - `./scripts/local_prod_checklist.sh` -> `ok`;
    - `uv run --package framework pytest core/framework/server/tests/test_api.py -q` -> `176 passed`;
    - `uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q` -> `28 passed`;
    - `uv run --no-project python scripts/autonomous_delivery_e2e_smoke.py` -> `status=ok`.
  - ops/health summary after gates confirms:
    - `stuck_runs_total=0`,
    - `no_progress_projects_total=0`,
    - `loop_stale=false`.
- Done when:
  - все gate-команды проходят в container-first режиме;
  - ops summary подтверждает `stuck=0/no_progress=0/loop_stale=false`.

240. `P1` Upstream Wave 3 - Cutover and Post-Merge Operator Sign-off
- Status: `done`
- Scope:
  - выполнить cutover на обновленную ветку и пересобрать runtime контейнеры;
  - пройти post-merge operator sign-off (Web + Telegram smoke + ops health).
- Progress:
  - cutover rebuild executed:
    - `docker compose up -d --build hive-core hive-scheduler` -> completed.
  - post-cutover runtime checks:
    - `docker compose ps` -> `hive-core/hive-scheduler/redis/postgres` healthy;
    - `/api/health` -> `status=ok`, telegram bridge running;
    - `/api/telegram/bridge/status` -> `status=ok`;
    - `/api/autonomous/ops/status?project_id=default&include_runs=true` -> `status=ok`.
  - operator sign-off artifact generated:
    - `uv run --no-project python scripts/telegram_operator_signoff.py ...` ->
      `docs/ops/telegram-signoff/latest.{json,md}`;
    - machine checks `ok`, manual checklist now `pass`;
    - latest sign-off evidence:
      - `docs/ops/telegram-signoff/latest.md` (`overall_status=pass`, `generated_at=2026-04-19T19:19:48Z`).
- Done when:
  - docker deployment green после cutover;
  - Telegram/Web operational smoke подтверждены;
  - backlog wave закрыт evidence-записями.

# Hive Official Docs Map (As-Is, 2026-04-07)

Карта основана на официальных источниках Hive/Aden и отражает текущую структуру портала и практический workflow.

## 1) Главный официальный ресурс

- Документация: `https://docs.adenhq.com/`
- Репозиторий: `https://github.com/aden-hive/hive`

## 2) Документированный путь разработки (official flow)

По официальной документации базовый путь такой:

1. Установить Hive (`./quickstart.sh`)
2. Сгенерировать агента через coding-agent workflow (`/hive`)
3. Прогнать тестирование (`/hive-test`, `pytest`, `hive test-run`)
4. Запустить и отладить (`hive run`, `hive tui`, `hive logs`)
5. Деплой (Local Docker / Aden Cloud / Autonomous mode)
6. Итерация и эволюция на основе outcomes

Ключевые страницы:

- Introduction: `https://docs.adenhq.com/`
- First agent: `https://docs.adenhq.com/building/first-agent`
- Goals: `https://docs.adenhq.com/building/goals`
- Nodes: `https://docs.adenhq.com/building/nodes`
- Edges: `https://docs.adenhq.com/building/edges`
- HITL: `https://docs.adenhq.com/building/human-in-the-loop`
- Testing: `https://docs.adenhq.com/building/testing`
- Debugging: `https://docs.adenhq.com/building/debugging`
- Deployment: `https://docs.adenhq.com/building/deployment`
- Iteration: `https://docs.adenhq.com/building/iteration`

## 3) Концепты, на которых строится подход

- Goal/Outcome-centric разработка: `https://docs.adenhq.com/building-agent/concepts/outcome-driven-development`
- Agent graph (nodes/edges/memory/HITL): `https://docs.adenhq.com/building-agent/concepts/agent-graph`
- Архитектура и SDK-wrapped nodes: `https://docs.adenhq.com/building-agent/concepts/agent-architecture`
- Worker model: `https://docs.adenhq.com/building-agent/concepts/worker-agent`
- Evolution loop: `https://docs.adenhq.com/building-agent/concepts/evolution`

## 4) Credentials и интеграции

- Credential Store (локально, encrypted storage, provider model): `https://docs.adenhq.com/building/credential-store`
- Aden Credential Sync (sync/refresh/validate через Aden API): `https://docs.adenhq.com/building/aden-credential-sync`

Практическая рекомендация из docs:

- локально: encrypted credential storage + provider logic;
- cloud/managed: sync/refresh через Aden.

## 5) Официально задокументированные MCP server names

На странице Codex setup явно указаны server entries:

- `agent-builder`
- `tools`

Источник: `https://docs.adenhq.com/building-agent/ai-tools/codex` (раздел `MCP Server Configuration`).

## 6) Что важно для нашего production-local сценария

- Local Docker deployment в docs считается first-class режимом.
- Для надежности упор на:
  - pre-flight validation,
  - runtime guardrails (cost/timeouts/escalations/HITL),
  - three-level observability,
  - итерационный цикл после деплоя.

## 7) Нюанс по разделу Coding Agents

Официально есть страницы для:

- Codex: `https://docs.adenhq.com/building-agent/ai-tools/codex`
- Claude Code: `https://docs.adenhq.com/building-agent/ai-tools/claude-code`
- Cursor: `https://docs.adenhq.com/building-agent/ai-tools/cursor`
- Windsurf: `https://docs.adenhq.com/building-agent/ai-tools/windsurf`

На практике самая детальная и консистентная MCP-конфигурация на текущем портале показана в Codex setup; остальные editor pages местами менее конкретны и требуют сверки с репозиторием.

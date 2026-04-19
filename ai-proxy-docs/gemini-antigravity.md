# Gemini Proxy: `proxy.thepeace.ru` (Antigravity-Manager)

## Назначение

Проксирование Gemini-моделей через Antigravity-Manager в OpenAI-совместимом формате.

## Ключи и конфиг

- `GEMINI_API_BASE=https://proxy.thepeace.ru/v1`
- `GEMINI_API_KEY=sk-...` (user token для Antigravity API)

## Как работает в Hive

Для моделей `gemini/...` или `google/...` Hive автоматически:

1. Переключает модель на `openai/<gemini-model>`.
2. Ставит `api_base=$GEMINI_API_BASE`.
3. Отправляет OpenAI-compatible запросы в Antigravity.

Реализация:
- [litellm.py](/Users/r2d2/Documents/Code_Projects/00_mcp/hive/core/framework/llm/litellm.py:620)
- [litellm.py](/Users/r2d2/Documents/Code_Projects/00_mcp/hive/core/framework/llm/litellm.py:651)

## Проверка работоспособности

```bash
curl "$GEMINI_API_BASE/chat/completions" \
  -H "Authorization: Bearer $GEMINI_API_KEY" \
  -H "content-type: application/json" \
  --data '{"model":"gemini-3.1-pro-high","messages":[{"role":"user","content":"reply with ok"}]}'
```

Ожидаемо: `HTTP 200` и ответ модели.

## Когда применять

- Все задачи на Gemini-моделях в этом проекте.
- Нужны внутренние пул/квоты/ротация аккаунтов Antigravity.

## Типовые проблемы

- `UserToken rejected`: неверный `GEMINI_API_KEY`.
- `503 Token error: All accounts failed or unhealthy`: проблема пула аккаунтов/квот Antigravity, не маршрутизации Hive.

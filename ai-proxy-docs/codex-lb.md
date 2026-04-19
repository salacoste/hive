# OpenAI/Codex Proxy: `codex.thepeace.ru` (codex-lb)

## Назначение

OpenAI-compatible балансировщик для GPT/Codex моделей.

## Ключи и конфиг

- `OPENAI_API_BASE=https://codex.thepeace.ru/v1`
- `OPENAI_API_KEY=codex-lb:...` (client API key в codex-lb)

Формат запросов: OpenAI-compatible (`/v1/models`, `/v1/chat/completions`).

## Как работает

1. Hive отправляет OpenAI-совместимый запрос в `codex.thepeace.ru`.
2. codex-lb валидирует входной client key.
3. codex-lb выбирает доступный upstream account и отправляет запрос.

## Проверка работоспособности

```bash
curl "$OPENAI_API_BASE/models" \
  -H "Authorization: Bearer $OPENAI_API_KEY"

curl "$OPENAI_API_BASE/chat/completions" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "content-type: application/json" \
  --data '{"model":"gpt-5.4","messages":[{"role":"user","content":"reply with ok"}]}'
```

Ожидаемо: `HTTP 200`.

## Когда применять

- GPT/Codex-поток проекта.
- Нужна единая точка доступа к OpenAI-подобным моделям и ротация аккаунтов.

## Типовые проблемы

- `401 invalid_api_key`: client key не зарегистрирован в `api_keys` таблице codex-lb.
- `503 no_plan_support_for_model`: запрошенная модель не поддерживается активными аккаунтами.

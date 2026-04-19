# Claude Proxy: `claude.thepeace.ru` (Clove)

## Назначение

Проксирование Anthropic API через ваш Clove, где upstream-аутентификация выполняется через Claude Code subscription.

## Ключи и конфиг

- `ANTHROPIC_API_BASE=https://claude.thepeace.ru`
- `ANTHROPIC_API_KEY=clv-...` (proxy key для входа в Clove)

Формат запросов: Anthropic Messages API (`POST /v1/messages`).

## Как работает

1. Hive отправляет стандартный Anthropic-запрос в `claude.thepeace.ru`.
2. Clove валидирует `clv-` ключ.
3. Clove ходит в upstream Anthropic через аккаунт с Claude Code subscription (OAuth/cookie path).

## Проверка работоспособности

```bash
curl "$ANTHROPIC_API_BASE/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  --data '{"model":"claude-sonnet-4-5-20250929","max_tokens":24,"messages":[{"role":"user","content":"reply with ok"}]}'
```

Ожидаемо: `HTTP 200`.

## Когда применять

- Нужны модели Claude.
- Нужен единый контроль доступа через proxy-ключи.
- Нужна маршрутизация через ваш аккаунт с Claude Code subscription.

## Типовые проблемы

- `401 Invalid API key`: неверный `ANTHROPIC_API_KEY` (должен быть `clv-...`).
- `429` от upstream: исчерпан лимит аккаунта Claude/подписки.
- Аккаунт в Clove не в `auth_type=both`/нет валидного OAuth токена: ручной refresh на стороне Clove.

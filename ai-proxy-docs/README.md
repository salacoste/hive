# AI Proxy Docs

Единая документация по LLM-прокси, используемым в проекте Hive.

## Что подключено сейчас

| Канал | Endpoint | Протокол | Env ключи |
|---|---|---|---|
| Claude (Clove) | `https://claude.thepeace.ru` | Anthropic Messages API (`/v1/messages`) | `ANTHROPIC_API_KEY`, `ANTHROPIC_API_BASE` |
| OpenAI/Codex LB | `https://codex.thepeace.ru/v1` | OpenAI-compatible (`/v1/*`) | `OPENAI_API_KEY`, `OPENAI_API_BASE` |
| Gemini (Antigravity) | `https://proxy.thepeace.ru/v1` | OpenAI-compatible (`/v1/*`) | `GEMINI_API_KEY`, `GEMINI_API_BASE` |
| Z.AI (GLM) | `https://api.z.ai/api/coding/paas/v4` | OpenAI-compatible (`/chat/completions`) | `ZAI_API_KEY`, `ZAI_API_BASE` |

## Текущие настроенные значения (маскировано)

- `ANTHROPIC_API_KEY=clv-...`
- `ANTHROPIC_API_BASE=https://claude.thepeace.ru`
- `OPENAI_API_KEY=codex-lb:...`
- `OPENAI_API_BASE=https://codex.thepeace.ru/v1`
- `GEMINI_API_KEY=sk-...`
- `GEMINI_API_BASE=https://proxy.thepeace.ru/v1`
- `ZAI_API_KEY=4c15...`
- `ZAI_API_BASE=https://api.z.ai/api/coding/paas/v4`

Источник истины: [`.env`](/Users/r2d2/Documents/Code_Projects/00_mcp/hive/.env)

## Как выбрать канал

- Нужны Claude-модели и Claude Code-подписка: используем `claude.thepeace.ru` (Clove).
- Нужны GPT/Codex-модели: используем `codex.thepeace.ru`.
- Нужны Gemini-модели через ваш пул аккаунтов: используем `proxy.thepeace.ru`.
- Нужны GLM-модели (`glm-5.1` и т.д.): используем `api.z.ai`.

## Быстрые smoke-тесты

```bash
# Claude
curl "$ANTHROPIC_API_BASE/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  --data '{"model":"claude-sonnet-4-5-20250929","max_tokens":24,"messages":[{"role":"user","content":"ok"}]}'

# Codex/OpenAI
curl "$OPENAI_API_BASE/chat/completions" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "content-type: application/json" \
  --data '{"model":"gpt-5.4","messages":[{"role":"user","content":"ok"}]}'

# Gemini over proxy
curl "$GEMINI_API_BASE/chat/completions" \
  -H "Authorization: Bearer $GEMINI_API_KEY" \
  -H "content-type: application/json" \
  --data '{"model":"gemini-3.1-pro-high","messages":[{"role":"user","content":"ok"}]}'

# GLM
curl "$ZAI_API_BASE/chat/completions" \
  -H "Authorization: Bearer $ZAI_API_KEY" \
  -H "content-type: application/json" \
  --data '{"model":"glm-5.1","messages":[{"role":"user","content":"ok"}],"max_tokens":256}'
```

## Подробные runbook-файлы

- [claude-clove.md](/Users/r2d2/Documents/Code_Projects/00_mcp/hive/ai-proxy-docs/claude-clove.md)
- [codex-lb.md](/Users/r2d2/Documents/Code_Projects/00_mcp/hive/ai-proxy-docs/codex-lb.md)
- [gemini-antigravity.md](/Users/r2d2/Documents/Code_Projects/00_mcp/hive/ai-proxy-docs/gemini-antigravity.md)
- [zai-glm.md](/Users/r2d2/Documents/Code_Projects/00_mcp/hive/ai-proxy-docs/zai-glm.md)

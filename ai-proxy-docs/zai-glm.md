# Z.AI / GLM: `api.z.ai` (`glm-5.1`)

## Назначение

Доступ к моделям GLM (например `glm-5.1`) через OpenAI-compatible endpoint Z.AI.

## Ключи и конфиг

- `ZAI_API_KEY=...`
- `ZAI_API_BASE=https://api.z.ai/api/coding/paas/v4`

## Как работает в Hive

Для моделей `glm-*` и `z-ai/*` Hive автоматически:

1. Нормализует модель к `openai/<glm-model>`.
2. Подставляет `api_base=$ZAI_API_BASE`.
3. Использует `ZAI_API_KEY` (а не `OPENAI_API_KEY`) для этих моделей.

Реализация:
- [litellm.py](/Users/r2d2/Documents/Code_Projects/00_mcp/hive/core/framework/llm/litellm.py:612)
- [litellm.py](/Users/r2d2/Documents/Code_Projects/00_mcp/hive/core/framework/llm/litellm.py:667)
- [runner.py](/Users/r2d2/Documents/Code_Projects/00_mcp/hive/core/framework/runner/runner.py:1760)

## Проверка работоспособности

```bash
curl "$ZAI_API_BASE/chat/completions" \
  -H "Authorization: Bearer $ZAI_API_KEY" \
  -H "content-type: application/json" \
  --data '{"model":"glm-5.1","messages":[{"role":"user","content":"reply with ok"}],"max_tokens":256}'
```

Ожидаемо: `HTTP 200`, `model: glm-5.1`, текстовый ответ.

## Когда применять

- Нужны GLM-модели (`glm-5.1`) для reasoning/cost-профиля Z.AI.
- Не нужен прокси `thepeace.ru` для этого канала (это прямой provider endpoint).

## Типовые проблемы

- `BadRequestError: LLM Provider NOT provided` для `glm-*`: исправлено нормализацией в `openai/glm-*`.
- Пустой `content` при малом `max_tokens`: увеличьте `max_tokens` (GLM часто тратит токены в `reasoning_content`).

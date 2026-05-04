from __future__ import annotations

import pytest

from framework.llm.fallback import FallbackLLMProvider, get_fallback_status
from framework.llm.provider import LLMProvider, LLMResponse, Tool
from framework.llm.stream_events import FinishEvent, StreamErrorEvent, TextDeltaEvent, TextEndEvent


class _StubProvider(LLMProvider):
    def __init__(self, model: str, stream_events: list[object]) -> None:
        self.model = model
        self._stream_events = stream_events
        self.stream_calls = 0

    def complete(
        self,
        messages: list[dict[str, object]],
        system: str = "",
        tools: list[Tool] | None = None,
        max_tokens: int = 1024,
        response_format: dict[str, object] | None = None,
        json_mode: bool = False,
        max_retries: int | None = None,
    ) -> LLMResponse:
        return LLMResponse(content=self.model, model=self.model)

    async def stream(
        self,
        messages: list[dict[str, object]],
        system: str = "",
        tools: list[Tool] | None = None,
        max_tokens: int = 4096,
    ):
        self.stream_calls += 1
        for event in self._stream_events:
            yield event


class _CompleteProvider(LLMProvider):
    def __init__(self, model: str, error: str | None = None) -> None:
        self.model = model
        self.error = error
        self.complete_calls = 0
        self.acomplete_calls = 0
        self.last_max_retries: int | None = None

    def complete(
        self,
        messages: list[dict[str, object]],
        system: str = "",
        tools: list[Tool] | None = None,
        max_tokens: int = 1024,
        response_format: dict[str, object] | None = None,
        json_mode: bool = False,
        max_retries: int | None = None,
    ) -> LLMResponse:
        self.complete_calls += 1
        self.last_max_retries = max_retries
        if self.error is not None:
            raise RuntimeError(self.error)
        return LLMResponse(content=self.model, model=self.model)

    async def acomplete(
        self,
        messages: list[dict[str, object]],
        system: str = "",
        tools: list[Tool] | None = None,
        max_tokens: int = 1024,
        response_format: dict[str, object] | None = None,
        json_mode: bool = False,
        max_retries: int | None = None,
    ) -> LLMResponse:
        self.acomplete_calls += 1
        self.last_max_retries = max_retries
        if self.error is not None:
            raise RuntimeError(self.error)
        return LLMResponse(content=self.model, model=self.model)


@pytest.mark.asyncio
async def test_stream_falls_back_when_provider_emits_initial_error_event() -> None:
    primary = _StubProvider(
        "primary-model",
        [StreamErrorEvent(error="Error code: 405 - Method Not Allowed", recoverable=False)],
    )
    backup = _StubProvider(
        "backup-model",
        [
            TextDeltaEvent(content="ok", snapshot="ok"),
            TextEndEvent(full_text="ok"),
            FinishEvent(stop_reason="stop", model="backup-model"),
        ],
    )
    provider = FallbackLLMProvider([primary, backup])

    events = [event async for event in provider.stream(messages=[{"role": "user", "content": "ping"}])]

    assert primary.stream_calls == 1
    assert backup.stream_calls == 1
    assert all(not isinstance(event, StreamErrorEvent) for event in events)
    assert any(isinstance(event, FinishEvent) and event.model == "backup-model" for event in events)


@pytest.mark.asyncio
async def test_stream_does_not_fallback_after_partial_output() -> None:
    primary = _StubProvider(
        "primary-model",
        [
            TextDeltaEvent(content="partial", snapshot="partial"),
            StreamErrorEvent(error="late stream failure", recoverable=False),
        ],
    )
    backup = _StubProvider(
        "backup-model",
        [
            TextDeltaEvent(content="should-not-run", snapshot="should-not-run"),
            FinishEvent(stop_reason="stop", model="backup-model"),
        ],
    )
    provider = FallbackLLMProvider([primary, backup])

    events = [event async for event in provider.stream(messages=[{"role": "user", "content": "ping"}])]

    assert primary.stream_calls == 1
    assert backup.stream_calls == 0
    assert any(isinstance(event, StreamErrorEvent) and "late stream failure" in event.error for event in events)


def test_complete_rate_limit_prefers_glm_backup() -> None:
    primary = _CompleteProvider("claude-opus-4-6", error="429 No accounts are currently available")
    non_glm = _CompleteProvider("gemini/gemini-3.1-pro-high")
    glm = _CompleteProvider("openai/glm-5.1")
    provider = FallbackLLMProvider([primary, non_glm, glm])

    response = provider.complete(messages=[{"role": "user", "content": "ping"}])

    assert response.model == "openai/glm-5.1"
    assert primary.complete_calls == 1
    assert non_glm.complete_calls == 0
    assert glm.complete_calls == 1


def test_complete_uses_default_failover_retry_limit() -> None:
    primary = _CompleteProvider("claude-opus-4-6", error="rate limit")
    glm = _CompleteProvider("openai/glm-5.1")
    provider = FallbackLLMProvider([primary, glm])

    provider.complete(messages=[{"role": "user", "content": "ping"}])

    assert primary.last_max_retries == 3
    assert glm.last_max_retries == 3


def test_complete_records_fallback_attempt_chain() -> None:
    primary = _CompleteProvider("claude-opus-4-6", error="429 No accounts are currently available")
    glm = _CompleteProvider("openai/glm-5.1")
    provider = FallbackLLMProvider([primary, glm])

    response = provider.complete(messages=[{"role": "user", "content": "ping"}])
    status = get_fallback_status()
    chain = status["recent_attempt_chains"][-1]

    assert response.model == "openai/glm-5.1"
    assert chain["mode"] == "complete"
    assert chain["final_model"] == "openai/glm-5.1"
    assert chain["exhausted"] is False
    assert len(chain["attempts"]) == 2
    assert chain["attempts"][0]["model"] == "claude-opus-4-6"
    assert chain["attempts"][0]["result"] == "error"
    assert chain["attempts"][0]["rate_limit_like"] is True
    assert chain["attempts"][0]["fallback_to"] == "openai/glm-5.1"
    assert chain["attempts"][1]["model"] == "openai/glm-5.1"
    assert chain["attempts"][1]["result"] == "success"

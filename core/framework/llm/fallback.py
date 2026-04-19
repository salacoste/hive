"""Fallback LLM provider wrapper.

Retries with backup providers when the primary provider raises an exception.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from framework.llm.provider import LLMProvider, LLMResponse, Tool
from framework.llm.stream_events import (
    FinishEvent,
    ReasoningDeltaEvent,
    StreamErrorEvent,
    TextDeltaEvent,
    TextEndEvent,
    ToolCallEvent,
)

logger = logging.getLogger(__name__)


def _get_env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r, using default=%d", name, raw, default)
        return default
    return max(minimum, value)


# After these provider-level retries are exhausted, fail over to the next model.
FAILOVER_RETRY_LIMIT = _get_env_int("HIVE_LLM_FAILOVER_RETRIES", 3, minimum=0)
_RATE_LIMIT_MARKERS = (
    "429",
    "rate limit",
    "rate_limit",
    "quota",
    "too many requests",
    "no accounts are currently available",
    "503100",
    "503130",
    "service unavailable",
    "overloaded",
)


def _is_rate_limit_like_error(error: BaseException | str) -> bool:
    text = str(error).lower()
    return any(marker in text for marker in _RATE_LIMIT_MARKERS)


class FallbackLLMProvider(LLMProvider):
    """Wrap a primary LLM with one or more fallback providers."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("FallbackLLMProvider requires at least one provider")
        self._providers = providers
        self.model = getattr(providers[0], "model", "unknown")

    def _iter_with_fallback(self):
        yield from enumerate(self._providers)

    def _next_provider_index(self, current_idx: int, error: BaseException | str) -> int | None:
        """Return the next provider index, prioritizing GLM on rate-limit failures."""
        if current_idx + 1 >= len(self._providers):
            return None
        if not _is_rate_limit_like_error(error):
            return current_idx + 1

        glm_idx = next(
            (
                i
                for i in range(current_idx + 1, len(self._providers))
                if "glm" in str(getattr(self._providers[i], "model", "")).lower()
            ),
            None,
        )
        return glm_idx if glm_idx is not None else current_idx + 1

    def complete(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[Tool] | None = None,
        max_tokens: int = 1024,
        response_format: dict[str, Any] | None = None,
        json_mode: bool = False,
        max_retries: int | None = None,
    ) -> LLMResponse:
        last_exc: Exception | None = None
        effective_retries = max_retries if max_retries is not None else FAILOVER_RETRY_LIMIT
        idx = 0
        while idx < len(self._providers):
            provider = self._providers[idx]
            try:
                return provider.complete(
                    messages=messages,
                    system=system,
                    tools=tools,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    json_mode=json_mode,
                    max_retries=effective_retries,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                next_idx = self._next_provider_index(idx, exc)
                if next_idx is not None:
                    logger.warning(
                        "Primary model '%s' failed (%s). Falling back to '%s'.",
                        getattr(provider, "model", "unknown"),
                        exc.__class__.__name__,
                        getattr(self._providers[next_idx], "model", "unknown"),
                    )
                    idx = next_idx
                else:
                    logger.error(
                        "All fallback models failed. Last model '%s' error: %s",
                        getattr(provider, "model", "unknown"),
                        exc,
                    )
                    break
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No providers available")

    async def acomplete(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[Tool] | None = None,
        max_tokens: int = 1024,
        response_format: dict[str, Any] | None = None,
        json_mode: bool = False,
        max_retries: int | None = None,
    ) -> LLMResponse:
        last_exc: Exception | None = None
        effective_retries = max_retries if max_retries is not None else FAILOVER_RETRY_LIMIT
        idx = 0
        while idx < len(self._providers):
            provider = self._providers[idx]
            try:
                return await provider.acomplete(
                    messages=messages,
                    system=system,
                    tools=tools,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    json_mode=json_mode,
                    max_retries=effective_retries,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                next_idx = self._next_provider_index(idx, exc)
                if next_idx is not None:
                    logger.warning(
                        "Primary model '%s' failed (%s). Falling back to '%s'.",
                        getattr(provider, "model", "unknown"),
                        exc.__class__.__name__,
                        getattr(self._providers[next_idx], "model", "unknown"),
                    )
                    idx = next_idx
                else:
                    logger.error(
                        "All fallback models failed. Last model '%s' error: %s",
                        getattr(provider, "model", "unknown"),
                        exc,
                    )
                    break
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No providers available")

    async def stream(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[Tool] | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Any]:
        last_exc: Exception | None = None
        idx = 0
        while idx < len(self._providers):
            provider = self._providers[idx]
            fallback_requested = False
            emitted_substantive_event = False
            requested_next_idx: int | None = None
            try:
                async for event in provider.stream(
                    messages=messages,
                    system=system,
                    tools=tools,
                    max_tokens=max_tokens,
                ):
                    if isinstance(event, StreamErrorEvent):
                        # Some providers encode hard failures as StreamErrorEvent
                        # instead of raising. If nothing useful was streamed,
                        # fail over to the next model in chain.
                        next_idx = self._next_provider_index(idx, event.error)
                        if next_idx is not None and not emitted_substantive_event:
                            logger.warning(
                                "Stream model '%s' emitted error event; falling back to '%s'. "
                                "error=%s",
                                getattr(provider, "model", "unknown"),
                                getattr(self._providers[next_idx], "model", "unknown"),
                                event.error,
                            )
                            fallback_requested = True
                            requested_next_idx = next_idx
                            break
                        yield event
                        return
                    if isinstance(
                        event,
                        (
                            TextDeltaEvent,
                            TextEndEvent,
                            ToolCallEvent,
                            ReasoningDeltaEvent,
                            FinishEvent,
                        ),
                    ):
                        emitted_substantive_event = True
                    yield event
                if fallback_requested:
                    if requested_next_idx is not None:
                        idx = requested_next_idx
                    else:
                        idx += 1
                    continue
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                next_idx = self._next_provider_index(idx, exc)
                if next_idx is not None:
                    logger.warning(
                        "Stream model '%s' failed (%s). Falling back to '%s'.",
                        getattr(provider, "model", "unknown"),
                        exc.__class__.__name__,
                        getattr(self._providers[next_idx], "model", "unknown"),
                    )
                    idx = next_idx
                else:
                    logger.error(
                        "All fallback stream models failed. Last model '%s' error: %s",
                        getattr(provider, "model", "unknown"),
                        exc,
                    )
                    break
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No providers available")

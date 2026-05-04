"""Fallback LLM provider wrapper.

Retries with backup providers when the primary provider raises an exception.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
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
FALLBACK_STATUS_HISTORY_LIMIT = _get_env_int("HIVE_LLM_FALLBACK_STATUS_HISTORY_LIMIT", 50, minimum=1)
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


_FALLBACK_STATUS_LOCK = threading.Lock()
_FALLBACK_STATUS_HISTORY: deque[dict[str, Any]] = deque(maxlen=FALLBACK_STATUS_HISTORY_LIMIT)


def _provider_model(provider: LLMProvider) -> str:
    return str(getattr(provider, "model", "unknown"))


def _record_fallback_attempt_chain(entry: dict[str, Any]) -> None:
    with _FALLBACK_STATUS_LOCK:
        _FALLBACK_STATUS_HISTORY.append(entry)


def get_fallback_status() -> dict[str, Any]:
    """Return recent fallback attempt chains for runtime observability."""
    with _FALLBACK_STATUS_LOCK:
        history = list(_FALLBACK_STATUS_HISTORY)
    return {
        "policy": {
            "failover_retry_limit": FAILOVER_RETRY_LIMIT,
            "rate_limit_marker_count": len(_RATE_LIMIT_MARKERS),
            "rate_limit_prefer_glm": True,
        },
        "history_limit": FALLBACK_STATUS_HISTORY_LIMIT,
        "recent_attempt_chains": history,
    }


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
        attempts: list[dict[str, Any]] = []
        idx = 0
        while idx < len(self._providers):
            provider = self._providers[idx]
            attempts.append({"index": idx, "model": _provider_model(provider)})
            try:
                response = provider.complete(
                    messages=messages,
                    system=system,
                    tools=tools,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    json_mode=json_mode,
                    max_retries=effective_retries,
                )
                attempts[-1]["result"] = "success"
                _record_fallback_attempt_chain(
                    {
                        "mode": "complete",
                        "timestamp": time.time(),
                        "final_model": response.model,
                        "effective_retries": effective_retries,
                        "attempts": attempts,
                        "exhausted": False,
                    }
                )
                return response
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                attempts[-1]["result"] = "error"
                attempts[-1]["error_type"] = exc.__class__.__name__
                attempts[-1]["error"] = str(exc)
                attempts[-1]["rate_limit_like"] = _is_rate_limit_like_error(exc)
                next_idx = self._next_provider_index(idx, exc)
                if next_idx is not None:
                    attempts[-1]["fallback_to"] = _provider_model(self._providers[next_idx])
                    logger.warning(
                        "Primary model '%s' failed (%s). Falling back to '%s'.",
                        _provider_model(provider),
                        exc.__class__.__name__,
                        _provider_model(self._providers[next_idx]),
                    )
                    idx = next_idx
                else:
                    logger.error(
                        "All fallback models failed. Last model '%s' error: %s",
                        _provider_model(provider),
                        exc,
                    )
                    break
        _record_fallback_attempt_chain(
            {
                "mode": "complete",
                "timestamp": time.time(),
                "final_model": None,
                "effective_retries": effective_retries,
                "attempts": attempts,
                "exhausted": True,
                "last_error": str(last_exc) if last_exc is not None else "No providers available",
            }
        )
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
        attempts: list[dict[str, Any]] = []
        idx = 0
        while idx < len(self._providers):
            provider = self._providers[idx]
            attempts.append({"index": idx, "model": _provider_model(provider)})
            try:
                response = await provider.acomplete(
                    messages=messages,
                    system=system,
                    tools=tools,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    json_mode=json_mode,
                    max_retries=effective_retries,
                )
                attempts[-1]["result"] = "success"
                _record_fallback_attempt_chain(
                    {
                        "mode": "acomplete",
                        "timestamp": time.time(),
                        "final_model": response.model,
                        "effective_retries": effective_retries,
                        "attempts": attempts,
                        "exhausted": False,
                    }
                )
                return response
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                attempts[-1]["result"] = "error"
                attempts[-1]["error_type"] = exc.__class__.__name__
                attempts[-1]["error"] = str(exc)
                attempts[-1]["rate_limit_like"] = _is_rate_limit_like_error(exc)
                next_idx = self._next_provider_index(idx, exc)
                if next_idx is not None:
                    attempts[-1]["fallback_to"] = _provider_model(self._providers[next_idx])
                    logger.warning(
                        "Primary model '%s' failed (%s). Falling back to '%s'.",
                        _provider_model(provider),
                        exc.__class__.__name__,
                        _provider_model(self._providers[next_idx]),
                    )
                    idx = next_idx
                else:
                    logger.error(
                        "All fallback models failed. Last model '%s' error: %s",
                        _provider_model(provider),
                        exc,
                    )
                    break
        _record_fallback_attempt_chain(
            {
                "mode": "acomplete",
                "timestamp": time.time(),
                "final_model": None,
                "effective_retries": effective_retries,
                "attempts": attempts,
                "exhausted": True,
                "last_error": str(last_exc) if last_exc is not None else "No providers available",
            }
        )
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
        attempts: list[dict[str, Any]] = []
        idx = 0
        while idx < len(self._providers):
            provider = self._providers[idx]
            attempts.append({"index": idx, "model": _provider_model(provider)})
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
                            attempts[-1]["result"] = "stream_error_fallback"
                            attempts[-1]["error"] = event.error
                            attempts[-1]["rate_limit_like"] = _is_rate_limit_like_error(event.error)
                            attempts[-1]["fallback_to"] = _provider_model(self._providers[next_idx])
                            logger.warning(
                                "Stream model '%s' emitted error event; falling back to '%s'. "
                                "error=%s",
                                _provider_model(provider),
                                _provider_model(self._providers[next_idx]),
                                event.error,
                            )
                            fallback_requested = True
                            requested_next_idx = next_idx
                            break
                        attempts[-1]["result"] = "stream_error_returned"
                        attempts[-1]["error"] = event.error
                        attempts[-1]["rate_limit_like"] = _is_rate_limit_like_error(event.error)
                        _record_fallback_attempt_chain(
                            {
                                "mode": "stream",
                                "timestamp": time.time(),
                                "final_model": _provider_model(provider),
                                "effective_retries": None,
                                "attempts": attempts,
                                "exhausted": False,
                            }
                        )
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
                attempts[-1]["result"] = "success"
                _record_fallback_attempt_chain(
                    {
                        "mode": "stream",
                        "timestamp": time.time(),
                        "final_model": _provider_model(provider),
                        "effective_retries": None,
                        "attempts": attempts,
                        "exhausted": False,
                    }
                )
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                attempts[-1]["result"] = "error"
                attempts[-1]["error_type"] = exc.__class__.__name__
                attempts[-1]["error"] = str(exc)
                attempts[-1]["rate_limit_like"] = _is_rate_limit_like_error(exc)
                next_idx = self._next_provider_index(idx, exc)
                if next_idx is not None:
                    attempts[-1]["fallback_to"] = _provider_model(self._providers[next_idx])
                    logger.warning(
                        "Stream model '%s' failed (%s). Falling back to '%s'.",
                        _provider_model(provider),
                        exc.__class__.__name__,
                        _provider_model(self._providers[next_idx]),
                    )
                    idx = next_idx
                else:
                    logger.error(
                        "All fallback stream models failed. Last model '%s' error: %s",
                        _provider_model(provider),
                        exc,
                    )
                    break
        _record_fallback_attempt_chain(
            {
                "mode": "stream",
                "timestamp": time.time(),
                "final_model": None,
                "effective_retries": None,
                "attempts": attempts,
                "exhausted": True,
                "last_error": str(last_exc) if last_exc is not None else "No providers available",
            }
        )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No providers available")

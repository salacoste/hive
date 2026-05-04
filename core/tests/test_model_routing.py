from __future__ import annotations

from framework.model_routing import resolve_model_chain


def test_heavy_profile_includes_glm_terminal_fallback() -> None:
    chain = resolve_model_chain(profile="heavy")
    assert chain[:2] == ["claude-opus-4-6", "gpt-5.4"]
    assert "openai/glm-5.1" in chain


def test_resolve_model_chain_dedupes_preserving_order() -> None:
    chain = resolve_model_chain(
        explicit_model="openai/gemini-3.1-pro-high",
        profile="implementation",
        extra_fallback_models=["openai/glm-5.1", "openai/gemini-3.1-pro-high"],
    )
    assert chain == ["openai/gemini-3.1-pro-high", "openai/glm-5.1"]

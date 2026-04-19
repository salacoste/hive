from __future__ import annotations

from types import SimpleNamespace

from framework.llm.fallback import FallbackLLMProvider
from framework.runner.runner import AgentRunner


class _PrimaryProvider:
    def __init__(self) -> None:
        self.model = "openai/gemini-3.1-pro-high"
        self.api_base = "https://proxy.example/v1"


class _LiteLLMProviderStub:
    def __init__(self, model: str, api_key: str | None = None, api_base: str | None = None):
        _ = api_key
        normalized_model = model
        if model.startswith("gemini/"):
            normalized_model = "openai/" + model.split("/", 1)[1]
        elif model.startswith("glm-"):
            normalized_model = "openai/" + model
        self.model = normalized_model
        self.api_base = api_base or "https://proxy.example/v1"


def test_apply_model_fallback_chain_dedupes_normalized_provider_signatures(monkeypatch) -> None:
    runner = AgentRunner.__new__(AgentRunner)
    runner._llm = _PrimaryProvider()
    runner.task_profile = "implementation"
    runner.model = "openai/gemini-3.1-pro-high"
    runner._tool_registry = SimpleNamespace(cleanup=lambda: None)
    runner._temp_dir = None

    monkeypatch.setattr(
        "framework.runner.runner.resolve_model_chain",
        lambda **_kwargs: [
            "openai/gemini-3.1-pro-high",
            "gemini/gemini-3.1-pro-high",
            "glm-5.1",
        ],
    )
    monkeypatch.setattr("framework.runner.runner.get_hive_config", lambda: {})
    monkeypatch.setattr(
        "framework.runner.runner.resolve_model_connection",
        lambda _model, _cfg: {"api_key_env_var": None, "api_base": "https://proxy.example/v1", "api_base_env_var": None},
    )
    monkeypatch.setattr("framework.llm.litellm.LiteLLMProvider", _LiteLLMProviderStub)

    runner._apply_model_fallback_chain()

    assert isinstance(runner._llm, FallbackLLMProvider)
    models = [getattr(provider, "model", "") for provider in runner._llm._providers]
    assert models == ["openai/gemini-3.1-pro-high", "openai/glm-5.1"]

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from aiohttp import web

from framework.config import _PROVIDER_CRED_MAP
from framework.server.app import APP_KEY_CREDENTIAL_STORE, APP_KEY_MANAGER
from framework.server.routes_config import _hot_swap_sessions, _resolve_api_key


class _DummyCredentialStore:
    def __init__(self, values: dict[str, str]):
        self._values = values

    def get(self, credential_id: str) -> str | None:
        return self._values.get(credential_id)


class _DummyManager:
    def __init__(self, sessions: list[object]):
        self._sessions = sessions
        self._model: str | None = None

    def list_sessions(self) -> list[object]:
        return self._sessions


def test_resolve_api_key_prefers_credential_store_over_env(monkeypatch) -> None:
    provider = "openai"
    env_var = "OPENAI_API_KEY"
    monkeypatch.setenv(env_var, "env-key")

    cred_id = _PROVIDER_CRED_MAP[provider]
    app = web.Application()
    app[APP_KEY_CREDENTIAL_STORE] = _DummyCredentialStore({cred_id: "store-key"})

    request = SimpleNamespace(app=app)
    assert _resolve_api_key(provider, request) == "store-key"


def test_resolve_api_key_falls_back_to_env_when_store_empty(monkeypatch) -> None:
    provider = "openai"
    env_var = "OPENAI_API_KEY"
    monkeypatch.setenv(env_var, "env-key")

    app = web.Application()
    app[APP_KEY_CREDENTIAL_STORE] = _DummyCredentialStore({})

    request = SimpleNamespace(app=app)
    assert _resolve_api_key(provider, request) == "env-key"


def test_hot_swap_sessions_uses_typed_manager_appkey() -> None:
    llm_with_reconfigure = SimpleNamespace(reconfigure=MagicMock())
    session_a = SimpleNamespace(llm=llm_with_reconfigure)
    session_b = SimpleNamespace(llm=SimpleNamespace())  # no reconfigure
    session_c = SimpleNamespace(llm=None)
    manager = _DummyManager([session_a, session_b, session_c])

    app = web.Application()
    app[APP_KEY_MANAGER] = manager
    request = SimpleNamespace(app=app)

    swapped = _hot_swap_sessions(
        request=request,
        full_model="openai/gpt-5.4",
        api_key="secret",
        api_base="https://api.example.test/v1",
    )

    assert manager._model == "openai/gpt-5.4"
    assert swapped == 1
    llm_with_reconfigure.reconfigure.assert_called_once_with(
        "openai/gpt-5.4",
        api_key="secret",
        api_base="https://api.example.test/v1",
    )

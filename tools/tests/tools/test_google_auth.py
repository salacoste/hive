"""Tests for shared Google auth helper."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

from aden_tools.tools.google_auth import get_google_access_token_from_env_or_file


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_returns_env_token_when_fresh(monkeypatch):
    now = int(time.time())
    monkeypatch.setenv("GOOGLE_ACCESS_TOKEN", "env-token")
    monkeypatch.setenv("GOOGLE_TOKEN_EXPIRES_AT", str(now + 3600))
    monkeypatch.delenv("GOOGLE_ACCESS_TOKEN_FILE", raising=False)

    with patch("aden_tools.tools.google_auth._refresh_access_token") as mock_refresh:
        token = get_google_access_token_from_env_or_file()

    assert token == "env-token"
    mock_refresh.assert_not_called()


def test_refreshes_expired_env_token(monkeypatch):
    now = int(time.time())
    monkeypatch.setenv("GOOGLE_ACCESS_TOKEN", "stale-token")
    monkeypatch.setenv("GOOGLE_TOKEN_EXPIRES_AT", str(now - 60))
    monkeypatch.delenv("GOOGLE_ACCESS_TOKEN_FILE", raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rtok")

    refreshed = {"access_token": "fresh-token", "expires_in": 3600, "scope": "scope.a scope.b"}
    with patch(
        "aden_tools.tools.google_auth.urllib.request.urlopen",
        return_value=_FakeHTTPResponse(refreshed),
    ):
        token = get_google_access_token_from_env_or_file()

    assert token == "fresh-token"
    assert os.getenv("GOOGLE_ACCESS_TOKEN") == "fresh-token"
    assert int(os.getenv("GOOGLE_TOKEN_EXPIRES_AT", "0")) > now


def test_refreshes_expired_file_token_and_updates_metadata(monkeypatch, tmp_path: Path):
    now = int(time.time())
    token_file = tmp_path / "google_access_token"
    meta_file = tmp_path / "google_access_token.meta.json"
    token_file.write_text("stale-file-token\n", encoding="utf-8")
    meta_file.write_text(
        json.dumps({"expires_at": now - 10, "updated_at": now - 100}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("GOOGLE_ACCESS_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("GOOGLE_ACCESS_TOKEN_META_FILE", str(meta_file))
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rtok")

    refreshed = {"access_token": "fresh-file-token", "expires_in": 1800}
    with patch(
        "aden_tools.tools.google_auth.urllib.request.urlopen",
        return_value=_FakeHTTPResponse(refreshed),
    ):
        token = get_google_access_token_from_env_or_file()

    assert token == "fresh-file-token"
    assert token_file.read_text(encoding="utf-8").strip() == "fresh-file-token"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert int(meta["expires_at"]) > now
    assert int(meta["updated_at"]) >= now


def test_returns_existing_token_when_refresh_fails(monkeypatch):
    now = int(time.time())
    monkeypatch.setenv("GOOGLE_ACCESS_TOKEN", "stale-token")
    monkeypatch.setenv("GOOGLE_TOKEN_EXPIRES_AT", str(now - 60))
    monkeypatch.delenv("GOOGLE_ACCESS_TOKEN_FILE", raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rtok")

    with patch(
        "aden_tools.tools.google_auth.urllib.request.urlopen",
        side_effect=RuntimeError("refresh down"),
    ):
        token = get_google_access_token_from_env_or_file()

    assert token == "stale-token"

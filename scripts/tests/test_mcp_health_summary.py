from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import subprocess
import time
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "mcp_health_summary.py"
SPEC = spec_from_file_location("mcp_health_summary", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture(autouse=True)
def _clear_google_env(monkeypatch) -> None:
    for name in (
        "GOOGLE_ACCESS_TOKEN_FILE",
        "GOOGLE_ACCESS_TOKEN_META_FILE",
        "GOOGLE_ACCESS_TOKEN",
        "GOOGLE_TOKEN_EXPIRES_AT",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REFRESH_TOKEN",
        "HIVE_GOOGLE_TOKEN_WARN_TTL_SECONDS",
        "HIVE_GOOGLE_TOKEN_CRITICAL_TTL_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_google_freshness_levels() -> None:
    now = int(time.time())
    warning = MODULE._google_freshness(
        expires_at=now + 200,
        warn_ttl_seconds=300,
        critical_ttl_seconds=120,
    )
    assert warning["known"] is True
    assert warning["level"] == "warning"

    critical = MODULE._google_freshness(
        expires_at=now + 30,
        warn_ttl_seconds=300,
        critical_ttl_seconds=120,
    )
    assert critical["level"] == "critical"

    unknown = MODULE._google_freshness(
        expires_at=None,
        warn_ttl_seconds=300,
        critical_ttl_seconds=120,
    )
    assert unknown["known"] is False
    assert unknown["level"] == "unknown"


def test_resolve_google_token_source_prefers_file(tmp_path: Path, monkeypatch) -> None:
    token_file = tmp_path / "google_access_token"
    meta_file = tmp_path / "google_access_token.meta.json"
    token_file.write_text("file-token\n", encoding="utf-8")
    meta_file.write_text('{"expires_at": 9999999999}\n', encoding="utf-8")

    for name in (
        "GOOGLE_ACCESS_TOKEN_FILE",
        "GOOGLE_ACCESS_TOKEN_META_FILE",
        "GOOGLE_ACCESS_TOKEN",
        "GOOGLE_TOKEN_EXPIRES_AT",
    ):
        monkeypatch.delenv(name, raising=False)

    env_map = {
        "GOOGLE_ACCESS_TOKEN_FILE": str(token_file),
        "GOOGLE_ACCESS_TOKEN_META_FILE": str(meta_file),
        "GOOGLE_ACCESS_TOKEN": "env-token-should-not-win",
        "GOOGLE_TOKEN_EXPIRES_AT": "1",
    }
    resolved = MODULE._resolve_google_access_token_source(env_map)
    assert resolved["source"] == "file"
    assert resolved["token"] == "file-token"
    assert int(resolved["expires_at"]) == 9999999999


def test_google_health_warning_stays_ok(monkeypatch) -> None:
    now = int(time.time())
    env_map = {
        "GOOGLE_ACCESS_TOKEN": "token-1",
        "GOOGLE_TOKEN_EXPIRES_AT": str(now + 180),
        "HIVE_GOOGLE_TOKEN_WARN_TTL_SECONDS": "300",
        "HIVE_GOOGLE_TOKEN_CRITICAL_TTL_SECONDS": "120",
    }
    monkeypatch.setattr(
        MODULE,
        "_google_tokeninfo_check",
        lambda _token: {"ok": True, "code": 200, "detail": "HTTP 200", "payload": {"expires_in": "180"}},
    )
    result = MODULE._google_health_check(env_map)
    assert result["ok"] is True
    assert result["detail"]["mode"] == "access_token"
    assert result["detail"]["freshness"]["level"] == "warning"


def test_google_health_critical_degrades(monkeypatch) -> None:
    now = int(time.time())
    env_map = {
        "GOOGLE_ACCESS_TOKEN": "token-2",
        "GOOGLE_TOKEN_EXPIRES_AT": str(now + 30),
        "HIVE_GOOGLE_TOKEN_WARN_TTL_SECONDS": "300",
        "HIVE_GOOGLE_TOKEN_CRITICAL_TTL_SECONDS": "120",
    }
    monkeypatch.setattr(
        MODULE,
        "_google_tokeninfo_check",
        lambda _token: {"ok": True, "code": 200, "detail": "HTTP 200", "payload": {"expires_in": "30"}},
    )
    result = MODULE._google_health_check(env_map)
    assert result["ok"] is False
    assert result["detail"]["freshness"]["level"] == "critical"


def test_google_health_refresh_fallback_reports_source_and_freshness(monkeypatch) -> None:
    env_map = {
        "GOOGLE_CLIENT_ID": "cid",
        "GOOGLE_CLIENT_SECRET": "csec",
        "GOOGLE_REFRESH_TOKEN": "rtok",
        "HIVE_GOOGLE_TOKEN_WARN_TTL_SECONDS": "900",
        "HIVE_GOOGLE_TOKEN_CRITICAL_TTL_SECONDS": "120",
    }
    monkeypatch.setattr(MODULE, "_refresh_google_access_token", lambda **_: ("refreshed-token", 3600))
    monkeypatch.setattr(
        MODULE,
        "_google_tokeninfo_check",
        lambda _token: {"ok": True, "code": 200, "detail": "HTTP 200", "payload": {"expires_in": "3600"}},
    )

    result = MODULE._google_health_check(env_map)
    assert result["ok"] is True
    assert result["detail"]["mode"] == "refresh_fallback"
    assert result["detail"]["token_source"] == "refresh_fallback"
    assert result["detail"]["freshness"]["level"] == "ok"


def test_files_tools_log_check_skips_when_docker_cli_unavailable(monkeypatch) -> None:
    def _missing_docker(*_args, **_kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(MODULE.subprocess, "run", _missing_docker)
    result = MODULE._files_tools_log_check(20)
    assert result["ok"] is True
    detail = result["detail"]
    assert isinstance(detail, dict)
    assert detail.get("mode") == "docker_cli_unavailable"
    assert detail.get("since_minutes") == 20


def test_files_tools_log_check_marks_failure_detected(monkeypatch) -> None:
    class _Proc:
        returncode = 0
        stdout = "Connected to MCP server 'files-tools'\nMCP server 'files-tools' failed to register"
        stderr = ""

    monkeypatch.setattr(MODULE.subprocess, "run", lambda *_a, **_k: _Proc())
    result = MODULE._files_tools_log_check(15)
    assert result["ok"] is False
    detail = result["detail"]
    assert isinstance(detail, dict)
    assert detail.get("mode") == "failure_detected"


def test_load_dotenv_fallback_without_python_dotenv(monkeypatch, tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "# comment",
                "PLAIN=value",
                "export EXPORTED=42",
                "QUOTED_SINGLE='abc def'",
                'QUOTED_DOUBLE="xyz"',
                "EMPTY=",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "_DOTENV_VALUES", None)
    values = MODULE._load_dotenv(dotenv_path)
    assert values["PLAIN"] == "value"
    assert values["EXPORTED"] == "42"
    assert values["QUOTED_SINGLE"] == "abc def"
    assert values["QUOTED_DOUBLE"] == "xyz"
    assert values["EMPTY"] == ""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

MODULE_PATH = Path(__file__).resolve().parents[1] / "telegram_chat_id_probe.py"
SPEC = spec_from_file_location("telegram_chat_id_probe", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_extract_chat_ids_from_message_and_callback() -> None:
    payload = {
        "result": [
            {"message": {"chat": {"id": 111}}},
            {"edited_message": {"chat": {"id": 222}}},
            {"callback_query": {"message": {"chat": {"id": 333}}}},
            {"message": {"chat": {"id": 111}}},
        ]
    }
    assert MODULE._extract_chat_ids(payload) == [111, 222, 333]


def test_extract_chat_ids_ignores_invalid_entries() -> None:
    payload = {"result": [{"message": {}}, {"callback_query": {}}, {"message": {"chat": {"id": "abc"}}}]}
    assert MODULE._extract_chat_ids(payload) == []


def test_write_alert_env_updates_primary_and_test_chat_id(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("TELEGRAM_BOT_TOKEN=test-token\n", encoding="utf-8")

    monkeypatch.setattr(
        MODULE,
        "_get_updates",
        lambda *_args, **_kwargs: {
            "result": [{"message": {"chat": {"id": 188207447}}}, {"message": {"chat": {"id": 42}}}]
        },
    )

    rc = MODULE.main(
        [
            "--dotenv",
            str(env_path),
            "--attempts",
            "1",
            "--timeout",
            "0",
            "--write-alert-env",
        ]
    )
    assert rc == 0
    content = env_path.read_text(encoding="utf-8")
    assert "GOOGLE_REFRESH_ALERT_CHAT_IDS=188207447,42" in content
    assert "HIVE_TELEGRAM_TEST_CHAT_ID=188207447" in content

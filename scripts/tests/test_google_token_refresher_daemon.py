from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

MODULE_PATH = Path(__file__).resolve().parents[1] / "google_token_refresher_daemon.py"
SPEC = spec_from_file_location("google_token_refresher_daemon", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_split_chat_ids() -> None:
    assert MODULE._split_chat_ids("1, 2, ,3") == ["1", "2", "3"]
    assert MODULE._split_chat_ids("") == []


def test_resolve_alert_chat_ids_raw_fallback_order(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_REFRESH_ALERT_CHAT_IDS", "")
    monkeypatch.setenv("GOOGLE_REFRESH_ALERT_CHAT_ID", "")
    monkeypatch.setenv("HIVE_TELEGRAM_TEST_CHAT_ID", "188207447")
    assert MODULE._resolve_alert_chat_ids_raw() == "188207447"

    monkeypatch.setenv("GOOGLE_REFRESH_ALERT_CHAT_ID", "legacy")
    assert MODULE._resolve_alert_chat_ids_raw() == "legacy"

    monkeypatch.setenv("GOOGLE_REFRESH_ALERT_CHAT_IDS", "1,2")
    assert MODULE._resolve_alert_chat_ids_raw() == "1,2"


def test_should_send_alert_threshold_and_cooldown() -> None:
    assert (
        MODULE._should_send_alert(
            consecutive_failures=2,
            threshold=3,
            last_alert_at=0,
            cooldown_seconds=3600,
            now=1000,
        )
        is False
    )
    assert (
        MODULE._should_send_alert(
            consecutive_failures=3,
            threshold=3,
            last_alert_at=0,
            cooldown_seconds=3600,
            now=1000,
        )
        is True
    )
    assert (
        MODULE._should_send_alert(
            consecutive_failures=4,
            threshold=3,
            last_alert_at=900,
            cooldown_seconds=3600,
            now=1000,
        )
        is False
    )
    assert (
        MODULE._should_send_alert(
            consecutive_failures=4,
            threshold=3,
            last_alert_at=0,
            cooldown_seconds=3600,
            now=5000,
        )
        is True
    )


def test_load_state_defaults_when_file_missing(tmp_path: Path) -> None:
    state = MODULE._load_state(tmp_path / "missing.json")
    assert state["consecutive_failures"] == 0
    assert state["total_failures"] == 0
    assert state["last_alert_at"] == 0


def test_load_state_reads_existing_values(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "consecutive_failures": 5,
                "total_failures": 9,
                "last_alert_at": 111,
                "last_alert_status": "sent",
            }
        ),
        encoding="utf-8",
    )
    state = MODULE._load_state(path)
    assert state["consecutive_failures"] == 5
    assert state["total_failures"] == 9
    assert state["last_alert_at"] == 111
    assert state["last_alert_status"] == "sent"


def test_send_failure_alert_if_needed_updates_state(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []

    def fake_send(bot_token: str, chat_id: str, text: str):
        calls.append((bot_token, chat_id, text))
        return True, "http=200"

    monkeypatch.setattr(MODULE, "_send_telegram_message", fake_send)
    state: dict[str, int | str] = {
        "consecutive_failures": 3,
        "last_alert_at": 0,
        "last_alert_status": "",
    }
    sent, detail = MODULE._send_failure_alert_if_needed(
        state=state,
        alert_enabled=True,
        threshold=3,
        cooldown_seconds=3600,
        bot_token="bot",
        chat_ids=["111", "222"],
        error_text="sample error",
        now=1234,
    )
    assert sent is True
    assert detail == "sent"
    assert state["last_alert_at"] == 1234
    assert state["last_alert_status"] == "sent"
    assert len(calls) == 2


def test_send_failure_alert_if_needed_missing_config(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "_send_telegram_message", lambda *_: (True, "http=200"))
    state: dict[str, int | str] = {
        "consecutive_failures": 4,
        "last_alert_at": 0,
    }
    sent, detail = MODULE._send_failure_alert_if_needed(
        state=state,
        alert_enabled=True,
        threshold=3,
        cooldown_seconds=3600,
        bot_token="",
        chat_ids=[],
        error_text="sample error",
        now=1234,
    )
    assert sent is False
    assert detail == "missing_telegram_config"

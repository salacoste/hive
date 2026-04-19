from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "autonomous_scheduler_daemon.py"
SPEC = spec_from_file_location("autonomous_scheduler_daemon", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_split_csv_normalizes_values() -> None:
    assert MODULE._split_csv("a, b ,, c") == ["a", "b", "c"]
    assert MODULE._split_csv("") == []


def test_parse_bool_accepts_truthy_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HIVE_FLAG", "yes")
    assert MODULE._parse_bool("HIVE_FLAG", False) is True
    monkeypatch.setenv("HIVE_FLAG", "0")
    assert MODULE._parse_bool("HIVE_FLAG", True) is False


def test_parse_int_rejects_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HIVE_INT", "abc")
    with pytest.raises(ValueError):
        MODULE._parse_int("HIVE_INT", 10, 1)


def test_build_run_cycle_payload_uses_project_filter() -> None:
    cfg = MODULE.SchedulerConfig(
        base_url="http://example",
        autonomous_enabled=True,
        autonomous_interval_seconds=120,
        autonomous_auto_start=True,
        autonomous_max_steps_per_project=3,
        autonomous_project_ids=["p1", "p2"],
        acceptance_enabled=True,
        acceptance_interval_seconds=3600,
        acceptance_project_id="default",
        request_timeout_seconds=20,
        state_path="/tmp/hive_scheduler_state.json",
        heartbeat_interval_seconds=5,
        session_id="",
        session_id_by_project={},
    )
    payload = MODULE._build_run_cycle_payload(cfg)
    assert payload["auto_start"] is True
    assert payload["max_steps_per_project"] == 3
    assert payload["project_ids"] == ["p1", "p2"]


def test_build_run_cycle_payload_prefers_session_map() -> None:
    cfg = MODULE.SchedulerConfig(
        base_url="http://example",
        autonomous_enabled=True,
        autonomous_interval_seconds=120,
        autonomous_auto_start=True,
        autonomous_max_steps_per_project=3,
        autonomous_project_ids=["p1"],
        acceptance_enabled=True,
        acceptance_interval_seconds=3600,
        acceptance_project_id="default",
        request_timeout_seconds=20,
        state_path="/tmp/hive_scheduler_state.json",
        heartbeat_interval_seconds=5,
        session_id="session_fallback",
        session_id_by_project={"p1": "session_project_1"},
    )
    payload = MODULE._build_run_cycle_payload(cfg)
    assert payload["session_id_by_project"] == {"p1": "session_project_1"}
    assert "session_id" not in payload

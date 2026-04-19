from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_backlog_status_json_contract.py"
SPEC = spec_from_file_location("check_backlog_status_json_contract", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_validate_payload_passes_for_valid_contract() -> None:
    payload = {
        "tasks_total": 2,
        "status_counts": {"todo": 0, "in_progress": 1, "blocked": 0, "done": 1, "unknown": 0},
        "in_progress": [2],
        "focus_refs": [2],
        "focus_items": [{"id": 2, "priority": "P2", "status": "in_progress", "title": "Task"}],
    }
    assert MODULE._validate_payload(payload) == []


def test_validate_payload_fails_for_invalid_contract() -> None:
    payload = {
        "tasks_total": 2,
        "status_counts": {"todo": 1, "in_progress": 0, "blocked": 0, "done": 0},
        "in_progress": [],
        "focus_refs": [1],
        "focus_items": [{"id": 2, "missing": True}],
    }
    errors = MODULE._validate_payload(payload)
    assert errors
    assert any("missing status_counts keys" in err for err in errors)


def test_main_fails_when_json_is_invalid(tmp_path: Path, monkeypatch, capsys) -> None:
    class Result:
        returncode = 0
        stdout = "not-json"
        stderr = ""

    script_path = tmp_path / "backlog_status.py"
    script_path.write_text("print('placeholder')\n", encoding="utf-8")
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_SCRIPT", script_path)
    monkeypatch.setattr(MODULE.subprocess, "run", lambda *args, **kwargs: Result())
    rc = MODULE.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "invalid JSON output" in out

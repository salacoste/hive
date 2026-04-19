from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_backlog_status_drift.py"
SPEC = spec_from_file_location("check_backlog_status_drift", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_drift_check_passes_when_live_matches_artifact(tmp_path: Path, monkeypatch, capsys) -> None:
    latest = tmp_path / "latest.json"
    validator = tmp_path / "validate_backlog_markdown.py"
    status_script = tmp_path / "backlog_status.py"
    validator.write_text("# placeholder\n", encoding="utf-8")
    status_script.write_text("# placeholder\n", encoding="utf-8")
    status = {
        "tasks_total": 3,
        "status_counts": {"todo": 0, "in_progress": 1, "blocked": 0, "done": 2, "unknown": 0},
        "in_progress": [3],
        "focus_refs": [3],
    }
    latest.write_text(json.dumps({"status": status}), encoding="utf-8")

    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_LATEST", latest)
    monkeypatch.setattr(MODULE, "VALIDATOR_SCRIPT", validator)
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_SCRIPT", status_script)
    monkeypatch.setattr(MODULE, "_run_backlog_validator", lambda: (0, "[ok]"))
    monkeypatch.setattr(MODULE, "_run_backlog_status_json", lambda: status)

    rc = MODULE.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "no drift between live backlog status and latest artifact" in out


def test_drift_check_fails_on_mismatch(tmp_path: Path, monkeypatch, capsys) -> None:
    latest = tmp_path / "latest.json"
    validator = tmp_path / "validate_backlog_markdown.py"
    status_script = tmp_path / "backlog_status.py"
    validator.write_text("# placeholder\n", encoding="utf-8")
    status_script.write_text("# placeholder\n", encoding="utf-8")
    latest.write_text(
        json.dumps(
            {
                "status": {
                    "tasks_total": 2,
                    "status_counts": {"todo": 0, "in_progress": 1, "blocked": 0, "done": 1, "unknown": 0},
                    "in_progress": [2],
                    "focus_refs": [2],
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_LATEST", latest)
    monkeypatch.setattr(MODULE, "VALIDATOR_SCRIPT", validator)
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_SCRIPT", status_script)
    monkeypatch.setattr(MODULE, "_run_backlog_validator", lambda: (0, "[ok]"))
    monkeypatch.setattr(
        MODULE,
        "_run_backlog_status_json",
        lambda: {
            "tasks_total": 3,
            "status_counts": {"todo": 0, "in_progress": 1, "blocked": 0, "done": 2, "unknown": 0},
            "in_progress": [3],
            "focus_refs": [3],
        },
    )

    rc = MODULE.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "drift detected between live backlog status and latest artifact" in out

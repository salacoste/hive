from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "backlog_status_artifact.py"
SPEC = spec_from_file_location("backlog_status_artifact", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_backlog_status_artifact_writes_timestamp_and_latest(tmp_path: Path, monkeypatch, capsys) -> None:
    output_dir = tmp_path / "artifacts"
    payload = {
        "tasks_total": 2,
        "status_counts": {"todo": 0, "in_progress": 1, "blocked": 0, "done": 1, "unknown": 0},
        "in_progress": [2],
        "focus_refs": [2],
        "focus_items": [{"id": 2, "priority": "P2", "status": "in_progress", "title": "Task"}],
    }
    script_path = tmp_path / "backlog_status.py"
    script_path.write_text("print('placeholder')\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_SCRIPT", script_path)
    monkeypatch.setattr(MODULE, "_load_status_payload", lambda: payload)

    rc = MODULE.main()
    assert rc == 0

    latest = output_dir / "latest.json"
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["status"]["tasks_total"] == 2

    snapshots = list(output_dir.glob("backlog-status-*.json"))
    assert len(snapshots) == 1

    out = capsys.readouterr().out
    assert "[ok] wrote" in out


def test_backlog_status_artifact_fails_when_script_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    script_path = tmp_path / "missing_script.py"
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_SCRIPT", script_path)
    rc = MODULE.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "[fail] missing script:" in out

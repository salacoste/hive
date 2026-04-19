from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "backlog_status.py"
SPEC = spec_from_file_location("backlog_status", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_backlog_status_text_output(tmp_path: Path, capsys) -> None:
    backlog = tmp_path / "backlog.md"
    backlog.write_text(
        "1. `P1` Build parser\n"
        "- Status: `done`\n"
        "2. `P2` Run checks\n"
        "- Status: `in_progress`\n"
        "## Current Focus (next execution wave)\n"
        "1. Execute item `2`\n",
        encoding="utf-8",
    )

    rc = MODULE.main(["--path", str(backlog)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "tasks_total=2" in out
    assert "in_progress=[2]" in out
    assert "focus_refs=[2]" in out
    assert " - 2: [P2] in_progress :: Run checks" in out


def test_backlog_status_json_output(tmp_path: Path, capsys) -> None:
    backlog = tmp_path / "backlog.md"
    backlog.write_text(
        "1. `P1` Task one\n"
        "- Status: `todo`\n"
        "2. `P2` Task two\n"
        "- Status: `blocked`\n"
        "## Current Focus (next execution wave)\n"
        "1. Execute item `2`\n",
        encoding="utf-8",
    )

    rc = MODULE.main(["--path", str(backlog), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tasks_total"] == 2
    assert payload["status_counts"]["todo"] == 1
    assert payload["status_counts"]["blocked"] == 1
    assert payload["in_progress"] == []
    assert payload["focus_refs"] == [2]
    assert payload["focus_items"] == [{"id": 2, "priority": "P2", "status": "blocked", "title": "Task two"}]


def test_backlog_status_fails_on_missing_file(capsys) -> None:
    rc = MODULE.main(["--path", "missing-file.md"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "[fail] backlog not found:" in out

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_backlog_status_consistency.py"
SPEC = spec_from_file_location("check_backlog_status_consistency", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_backlog_status_consistency_passes(tmp_path: Path, monkeypatch, capsys) -> None:
    backlog = tmp_path / "backlog.md"
    backlog.write_text(
        "1. `P1` First task\n"
        "- Status: `done`\n"
        "2. `P2` Second task\n"
        "- Status: `in_progress`\n"
        "## Current Focus (next execution wave)\n"
        "1. Execute item `2`\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "BACKLOG_PATH", backlog)
    rc = MODULE.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "task id sets in sync (2 tasks)" in out
    assert "backlog status parser and validator parser are consistent" in out


def test_backlog_status_consistency_fails_when_task_regex_drift_detected(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    backlog = tmp_path / "backlog.md"
    backlog.write_text(
        "1. `P1` \n"
        "- Status: `in_progress`\n"
        "## Current Focus (next execution wave)\n"
        "1. Execute item `1`\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "BACKLOG_PATH", backlog)
    rc = MODULE.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "task id sets diverged" in out

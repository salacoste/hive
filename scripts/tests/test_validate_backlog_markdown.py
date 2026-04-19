from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "validate_backlog_markdown.py"
SPEC = spec_from_file_location("validate_backlog_markdown", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _run_validator(tmp_path: Path, monkeypatch, content: str) -> int:
    backlog = tmp_path / "backlog.md"
    backlog.write_text(content, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["validate_backlog_markdown.py", str(backlog)])
    return MODULE.main()


def test_terminal_completion_all_done_allows_no_focus_and_no_in_progress(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    rc = _run_validator(
        tmp_path,
        monkeypatch,
        (
            "1. `P1` Finalize phase A\n"
            "- Status: `done`\n"
            "2. `P1` Finalize phase B\n"
            "- Status: `done`\n"
        ),
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "[ok] backlog validation passed" in out


def test_non_terminal_backlog_requires_in_progress_by_default(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    rc = _run_validator(
        tmp_path,
        monkeypatch,
        (
            "1. `P1` Finalize phase A\n"
            "- Status: `done`\n"
            "2. `P1` Finalize phase B\n"
            "- Status: `todo`\n"
        ),
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "at least one task must be in_progress" in out


from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_backlog_archive_index.py"
SPEC = spec_from_file_location("check_backlog_archive_index", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_check_passes_for_consistent_index(tmp_path: Path, monkeypatch, capsys) -> None:
    archive = tmp_path / "archive"
    archive.mkdir(parents=True)
    (archive / "backlog-done-snapshot-20260409-010203.md").write_text("# snap\n", encoding="utf-8")
    (archive / "INDEX.md").write_text(
        "# Backlog Archive Index\n\n"
        "| Snapshot | Timestamp |\n|---|---|\n"
        "| [backlog-done-snapshot-20260409-010203.md](backlog-done-snapshot-20260409-010203.md) | 2026-04-09 01:02:03 |\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(MODULE, "ARCHIVE_DIR", archive)
    monkeypatch.setattr(MODULE, "INDEX_PATH", archive / "INDEX.md")
    rc = MODULE.main()
    assert rc == 0
    assert "[ok] backlog archive index is consistent" in capsys.readouterr().out


def test_check_fails_for_unknown_and_mismatch(tmp_path: Path, monkeypatch, capsys) -> None:
    archive = tmp_path / "archive"
    archive.mkdir(parents=True)
    (archive / "backlog-done-snapshot-20260409-010203.md").write_text("# snap\n", encoding="utf-8")
    (archive / "INDEX.md").write_text(
        "# Backlog Archive Index\n\n"
        "| Snapshot | Timestamp |\n|---|---|\n"
        "| [backlog-done-snapshot-20260408-010203.md](backlog-done-snapshot-20260408-010203.md) | unknown |\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(MODULE, "ARCHIVE_DIR", archive)
    monkeypatch.setattr(MODULE, "INDEX_PATH", archive / "INDEX.md")
    rc = MODULE.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "index contains 'unknown'" in out
    assert "snapshots missing in index" in out
    assert "stale index references" in out

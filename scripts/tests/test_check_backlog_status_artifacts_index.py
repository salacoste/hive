from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_backlog_status_artifacts_index.py"
SPEC = spec_from_file_location("check_backlog_status_artifacts_index", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_check_passes_for_consistent_index(tmp_path: Path, monkeypatch, capsys) -> None:
    artifacts = tmp_path / "backlog-status"
    artifacts.mkdir(parents=True)
    (artifacts / "backlog-status-20260410-010203.json").write_text("{}\n", encoding="utf-8")
    (artifacts / "INDEX.md").write_text(
        "# Backlog Status Artifacts Index\n\n"
        "| Artifact |\n|---|\n"
        "| [backlog-status-20260410-010203.json](backlog-status-20260410-010203.json) |\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(MODULE, "ARTIFACT_DIR", artifacts)
    monkeypatch.setattr(MODULE, "INDEX_PATH", artifacts / "INDEX.md")
    rc = MODULE.main()
    assert rc == 0
    assert "[ok] backlog status artifacts index is consistent" in capsys.readouterr().out


def test_check_fails_for_missing_and_stale(tmp_path: Path, monkeypatch, capsys) -> None:
    artifacts = tmp_path / "backlog-status"
    artifacts.mkdir(parents=True)
    (artifacts / "backlog-status-20260410-010203.json").write_text("{}\n", encoding="utf-8")
    (artifacts / "INDEX.md").write_text(
        "# Backlog Status Artifacts Index\n\n"
        "| Artifact |\n|---|\n"
        "| [backlog-status-20260409-010203.json](backlog-status-20260409-010203.json) |\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(MODULE, "ARTIFACT_DIR", artifacts)
    monkeypatch.setattr(MODULE, "INDEX_PATH", artifacts / "INDEX.md")
    rc = MODULE.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "artifacts missing in index" in out
    assert "stale index references" in out

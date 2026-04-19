from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "backlog_status_hygiene.py"
SPEC = spec_from_file_location("backlog_status_hygiene", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_hygiene_preview_keeps_files_and_builds_index(tmp_path: Path, monkeypatch, capsys) -> None:
    out_dir = tmp_path / "backlog-status"
    out_dir.mkdir(parents=True, exist_ok=True)
    newest = out_dir / "backlog-status-20260410-100000.json"
    oldest = out_dir / "backlog-status-20260401-100000.json"
    newest.write_text("{}\n", encoding="utf-8")
    oldest.write_text("{}\n", encoding="utf-8")
    (out_dir / "latest.json").write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "OUT_DIR", out_dir)
    monkeypatch.setattr("sys.argv", ["backlog_status_hygiene.py", "--keep", "1"])
    rc = MODULE.main()
    assert rc == 0
    assert newest.exists()
    assert oldest.exists()
    index = out_dir / "INDEX.md"
    assert index.exists()
    out = capsys.readouterr().out
    assert "prune_candidates=1" in out
    assert "[guardrail] dry-run preview only" in out


def test_hygiene_apply_deletes_candidates(tmp_path: Path, monkeypatch, capsys) -> None:
    out_dir = tmp_path / "backlog-status"
    out_dir.mkdir(parents=True, exist_ok=True)
    keep = out_dir / "backlog-status-20260410-100000.json"
    drop = out_dir / "backlog-status-20260401-100000.json"
    keep.write_text("{}\n", encoding="utf-8")
    drop.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "OUT_DIR", out_dir)
    monkeypatch.setattr("sys.argv", ["backlog_status_hygiene.py", "--keep", "1", "--yes"])
    rc = MODULE.main()
    assert rc == 0
    assert keep.exists()
    assert not drop.exists()
    out = capsys.readouterr().out
    assert "deleted=1" in out

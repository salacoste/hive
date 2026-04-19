from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "acceptance_report_hygiene.py"
SPEC = spec_from_file_location("acceptance_report_hygiene", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_report(path: Path) -> None:
    path.write_text('{"generated_at":"2026-04-09T00:00:00"}\n', encoding="utf-8")


def test_hygiene_builds_index_and_preview_only(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_report(tmp_path / "acceptance-report-20260409-000001.json")
    _write_report(tmp_path / "acceptance-report-20260409-000002.json")

    monkeypatch.setattr(MODULE, "OUT_DIR", tmp_path)
    monkeypatch.setattr(MODULE, "PATTERN", "acceptance-report-*.json")
    monkeypatch.setattr("sys.argv", ["acceptance_report_hygiene.py", "--keep", "1"])

    rc = MODULE.main()
    assert rc == 0

    out = capsys.readouterr().out
    assert "prune_candidates=1" in out
    assert "deleted=0" in out
    assert "[guardrail] dry-run preview only" in out

    index_path = tmp_path / "INDEX.md"
    assert index_path.exists()
    index_text = index_path.read_text(encoding="utf-8")
    assert "Acceptance Reports Index" in index_text
    assert "acceptance-report-20260409-000002.json" in index_text


def test_hygiene_apply_prune_deletes_old_files(tmp_path: Path, monkeypatch, capsys) -> None:
    newest = tmp_path / "acceptance-report-20260409-000010.json"
    oldest = tmp_path / "acceptance-report-20260409-000001.json"
    _write_report(newest)
    _write_report(oldest)

    monkeypatch.setattr(MODULE, "OUT_DIR", tmp_path)
    monkeypatch.setattr(MODULE, "PATTERN", "acceptance-report-*.json")
    monkeypatch.setattr("sys.argv", ["acceptance_report_hygiene.py", "--keep", "1", "--yes"])

    rc = MODULE.main()
    assert rc == 0

    out = capsys.readouterr().out
    assert "deleted=1" in out
    assert newest.exists()
    assert not oldest.exists()

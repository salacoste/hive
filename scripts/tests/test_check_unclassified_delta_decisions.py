from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_unclassified_delta_decisions.py"
SPEC = spec_from_file_location("check_unclassified_delta_decisions", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_load_decisions_valid(tmp_path: Path) -> None:
    f = tmp_path / "decisions.json"
    f.write_text(
        (
            "{"
            "\"a.py\":{\"decision\":\"already-absorbed\",\"rationale\":\"ok\",\"backlog_items\":[109],\"validation\":[\"pytest a\"]},"
            "\"b.py\":{\"decision\":\"defer\",\"rationale\":\"later\",\"backlog_items\":[120],\"validation\":[\"pytest b\"]}"
            "}"
        ),
        encoding="utf-8",
    )
    data = MODULE.load_decisions(f)
    assert data["a.py"]["decision"] == "already-absorbed"
    assert data["b.py"]["decision"] == "defer"


def test_load_decisions_rejects_invalid_decision(tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text(
        "{\"a.py\":{\"decision\":\"unknown\",\"rationale\":\"x\",\"backlog_items\":[1],\"validation\":[\"pytest\"]}}",
        encoding="utf-8",
    )
    try:
        MODULE.load_decisions(f)
    except ValueError as exc:
        assert "invalid decision" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_main_fails_when_missing_decision(tmp_path: Path, monkeypatch, capsys) -> None:
    f = tmp_path / "decisions.json"
    f.write_text(
        "{\"only.py\":{\"decision\":\"already-absorbed\",\"rationale\":\"ok\",\"backlog_items\":[1],\"validation\":[\"pytest\"]}}",
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "DECISIONS_PATH", f)
    monkeypatch.setattr(MODULE, "get_unclassified_paths", lambda *_: ["only.py", "missing.py"])
    rc = MODULE.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing decisions" in out


def test_main_passes_and_reports_tally(tmp_path: Path, monkeypatch, capsys) -> None:
    f = tmp_path / "decisions.json"
    f.write_text(
        (
            "{"
            "\"a.py\":{\"decision\":\"already-absorbed\",\"rationale\":\"ok\",\"backlog_items\":[1],\"validation\":[\"pytest a\"]},"
            "\"b.py\":{\"decision\":\"defer\",\"rationale\":\"later\",\"backlog_items\":[2],\"validation\":[\"pytest b\"]}"
            "}"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "DECISIONS_PATH", f)
    monkeypatch.setattr(MODULE, "get_unclassified_paths", lambda *_: ["a.py", "b.py"])
    rc = MODULE.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "covered_unclassified=2" in out
    assert "decision_tally=" in out


def test_load_decisions_rejects_missing_backlog_items(tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text(
        "{\"a.py\":{\"decision\":\"already-absorbed\",\"rationale\":\"x\",\"validation\":[\"pytest\"]}}",
        encoding="utf-8",
    )
    try:
        MODULE.load_decisions(f)
    except ValueError as exc:
        assert "backlog_items" in str(exc)
    else:
        raise AssertionError("expected ValueError")

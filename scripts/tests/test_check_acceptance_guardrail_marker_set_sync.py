from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_acceptance_guardrail_marker_set_sync.py"
SPEC = spec_from_file_location("check_acceptance_guardrail_marker_set_sync", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_marker_set_sync_passes_when_sets_match(tmp_path: Path, monkeypatch, capsys) -> None:
    guards = tmp_path / "guards.py"
    docs = tmp_path / "docs.py"
    map_path = tmp_path / "map.md"
    guards.write_text('GUARDRAIL_SCRIPTS=["scripts/check_acceptance_docs_navigation.py"]\n', encoding="utf-8")
    docs.write_text(
        f'from pathlib import Path\nCHECKS=[(Path("{map_path.as_posix()}"), ["scripts/check_acceptance_docs_navigation.py"])]\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(MODULE, "GUARDRAILS_MODULE_PATH", guards)
    monkeypatch.setattr(MODULE, "DOCS_NAV_MODULE_PATH", docs)
    monkeypatch.setattr(MODULE, "DOCS_MAP_PATH", map_path)
    rc = MODULE.main()
    assert rc == 0
    assert "marker sets are in sync" in capsys.readouterr().out


def test_marker_set_sync_fails_when_drift_detected(tmp_path: Path, monkeypatch, capsys) -> None:
    guards = tmp_path / "guards.py"
    docs = tmp_path / "docs.py"
    map_path = tmp_path / "map.md"
    guards.write_text('GUARDRAIL_SCRIPTS=["scripts/check_acceptance_docs_navigation.py"]\n', encoding="utf-8")
    docs.write_text(
        f'from pathlib import Path\nCHECKS=[(Path("{map_path.as_posix()}"), ["scripts/check_acceptance_preset_contract_sync.py"])]\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(MODULE, "GUARDRAILS_MODULE_PATH", guards)
    monkeypatch.setattr(MODULE, "DOCS_NAV_MODULE_PATH", docs)
    monkeypatch.setattr(MODULE, "DOCS_MAP_PATH", map_path)
    rc = MODULE.main()
    assert rc == 1
    assert "guardrail marker-set sync failed" in capsys.readouterr().out

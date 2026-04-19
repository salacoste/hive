from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_acceptance_guardrails_sync.py"
SPEC = spec_from_file_location("check_acceptance_guardrails_sync", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_guardrails_sync_passes(tmp_path: Path, monkeypatch, capsys) -> None:
    self_check = tmp_path / "self_check.sh"
    map_doc = tmp_path / "map.md"
    markers = [
        "scripts/check_acceptance_gate_toggles_sync.py",
        "scripts/check_acceptance_docs_navigation.py",
        "scripts/check_acceptance_preset_contract_sync.py",
        "scripts/check_acceptance_preset_smoke_determinism.sh",
        "scripts/check_acceptance_runbook_sanity_sync.py",
        "scripts/check_acceptance_self_check_test_bundle_sync.py",
        "scripts/check_backlog_status_consistency.py",
        "scripts/check_backlog_status_json_contract.py",
        "scripts/check_backlog_status_drift.py",
        "scripts/check_backlog_status_artifacts_index.py",
        "scripts/check_backlog_archive_index.py",
    ]
    self_check.write_text("\n".join(markers) + "\n", encoding="utf-8")
    map_doc.write_text("\n".join(markers) + "\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "SELF_CHECK_PATH", self_check)
    monkeypatch.setattr(MODULE, "MAP_PATH", map_doc)
    monkeypatch.setattr(MODULE, "GUARDRAIL_SCRIPTS", markers)

    rc = MODULE.main()
    assert rc == 0
    assert "acceptance guardrails are in sync" in capsys.readouterr().out


def test_guardrails_sync_fails_on_missing_marker(tmp_path: Path, monkeypatch, capsys) -> None:
    self_check = tmp_path / "self_check.sh"
    map_doc = tmp_path / "map.md"
    self_check.write_text("scripts/check_acceptance_gate_toggles_sync.py\n", encoding="utf-8")
    map_doc.write_text("scripts/check_acceptance_gate_toggles_sync.py\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "SELF_CHECK_PATH", self_check)
    monkeypatch.setattr(MODULE, "MAP_PATH", map_doc)
    monkeypatch.setattr(MODULE, "GUARDRAIL_SCRIPTS", ["scripts/check_acceptance_docs_navigation.py"])

    rc = MODULE.main()
    assert rc == 1
    assert "guardrails sync mismatch" in capsys.readouterr().out

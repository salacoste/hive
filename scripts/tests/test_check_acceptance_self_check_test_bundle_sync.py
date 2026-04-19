from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_acceptance_self_check_test_bundle_sync.py"
SPEC = spec_from_file_location("check_acceptance_self_check_test_bundle_sync", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_bundle_sync_passes_when_all_modules_present(tmp_path: Path, monkeypatch, capsys) -> None:
    modules = [
        "scripts/tests/test_check_runbook_sync.py",
        "scripts/tests/test_acceptance_gate_presets.py",
    ]
    self_check = tmp_path / "self_check.sh"
    self_check.write_text("\n".join(modules) + "\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "SELF_CHECK_PATH", self_check)
    monkeypatch.setattr(MODULE, "REQUIRED_TEST_MODULES", modules)
    rc = MODULE.main()
    assert rc == 0
    assert "acceptance self-check test bundle is in sync" in capsys.readouterr().out


def test_bundle_sync_fails_when_module_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    self_check = tmp_path / "self_check.sh"
    self_check.write_text("scripts/tests/test_check_runbook_sync.py\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "SELF_CHECK_PATH", self_check)
    monkeypatch.setattr(
        MODULE,
        "REQUIRED_TEST_MODULES",
        ["scripts/tests/test_check_runbook_sync.py", "scripts/tests/test_acceptance_gate_presets.py"],
    )
    rc = MODULE.main()
    assert rc == 1
    assert "missing required test modules" in capsys.readouterr().out

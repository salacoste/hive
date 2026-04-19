from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_acceptance_preset_contract_sync.py"
SPEC = spec_from_file_location("check_acceptance_preset_contract_sync", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_preset_contract_sync_passes(tmp_path: Path, monkeypatch, capsys) -> None:
    preset = tmp_path / "preset.sh"
    smoke = tmp_path / "smoke.sh"
    docs = tmp_path / "map.md"
    preset.write_text(
        "fast)\nstrict)\nfull)\nfull-deep)\n[fast|strict|full|full-deep]\n",
        encoding="utf-8",
    )
    smoke.write_text(
        'run_step "preset fast print-only"\n'
        'run_step "preset strict print-only"\n'
        'run_step "preset full print-only"\n'
        'run_step "preset full-deep print-only"\n',
        encoding="utf-8",
    )
    docs.write_text(
        "./scripts/acceptance_gate_presets.sh fast\n"
        "./scripts/acceptance_gate_presets.sh strict\n"
        "./scripts/acceptance_gate_presets.sh full\n"
        "./scripts/acceptance_gate_presets.sh full-deep\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        MODULE,
        "CHECKS",
        [
            (preset, ["fast)", "strict)", "full)", "full-deep)", "[fast|strict|full|full-deep]"]),
            (
                smoke,
                [
                    'run_step "preset fast print-only"',
                    'run_step "preset strict print-only"',
                    'run_step "preset full print-only"',
                    'run_step "preset full-deep print-only"',
                ],
            ),
            (
                docs,
                [
                    "./scripts/acceptance_gate_presets.sh fast",
                    "./scripts/acceptance_gate_presets.sh strict",
                    "./scripts/acceptance_gate_presets.sh full",
                    "./scripts/acceptance_gate_presets.sh full-deep",
                ],
            ),
        ],
    )
    rc = MODULE.main()
    assert rc == 0
    assert "acceptance preset contract is in sync" in capsys.readouterr().out


def test_preset_contract_sync_fails_on_missing_marker(tmp_path: Path, monkeypatch, capsys) -> None:
    broken = tmp_path / "broken.sh"
    broken.write_text("fast)\nstrict)\n", encoding="utf-8")
    monkeypatch.setattr(MODULE, "CHECKS", [(broken, ["full-deep)"])])
    rc = MODULE.main()
    assert rc == 1
    assert "preset contract sync failed" in capsys.readouterr().out

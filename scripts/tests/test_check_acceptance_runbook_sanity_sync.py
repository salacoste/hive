from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_acceptance_runbook_sanity_sync.py"
SPEC = spec_from_file_location("check_acceptance_runbook_sanity_sync", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_runbook_sanity_sync_passes(tmp_path: Path, monkeypatch, capsys) -> None:
    runbook = tmp_path / "runbook.md"
    markers = [
        "uv run python scripts/check_acceptance_docs_navigation.py",
        "uv run python scripts/check_acceptance_gate_toggles_sync.py",
        "./scripts/check_acceptance_preset_smoke_determinism.sh",
    ]
    runbook.write_text("\n".join(markers) + "\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "RUNBOOK_PATH", runbook)
    monkeypatch.setattr(MODULE, "REQUIRED_COMMAND_MARKERS", markers)
    rc = MODULE.main()
    assert rc == 0
    assert "acceptance runbook sanity commands are in sync" in capsys.readouterr().out


def test_runbook_sanity_sync_fails_when_marker_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    runbook = tmp_path / "runbook.md"
    runbook.write_text("uv run python scripts/check_acceptance_docs_navigation.py\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "RUNBOOK_PATH", runbook)
    monkeypatch.setattr(
        MODULE,
        "REQUIRED_COMMAND_MARKERS",
        [
            "uv run python scripts/check_acceptance_docs_navigation.py",
            "uv run python scripts/check_acceptance_gate_toggles_sync.py",
        ],
    )
    rc = MODULE.main()
    assert rc == 1
    assert "missing runbook sanity markers" in capsys.readouterr().out

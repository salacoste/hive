from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_acceptance_gate_toggles_sync.py"
SPEC = spec_from_file_location("check_acceptance_gate_toggles_sync", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_toggles_sync_pass(tmp_path: Path, monkeypatch, capsys) -> None:
    gate = tmp_path / "gate.sh"
    runbook = tmp_path / "runbook.md"
    payload = "\n".join(MODULE.TOGGLES) + "\n"
    gate.write_text(payload, encoding="utf-8")
    runbook.write_text(payload, encoding="utf-8")

    monkeypatch.setattr(MODULE, "GATE", gate)
    monkeypatch.setattr(MODULE, "RUNBOOK", runbook)
    rc = MODULE.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "[ok] acceptance gate toggles are in sync" in out


def test_toggles_sync_fail_when_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    gate = tmp_path / "gate.sh"
    runbook = tmp_path / "runbook.md"
    gate.write_text("\n".join(MODULE.TOGGLES) + "\n", encoding="utf-8")
    runbook.write_text("only-some\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "GATE", gate)
    monkeypatch.setattr(MODULE, "RUNBOOK", runbook)
    rc = MODULE.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "[fail] toggle drift detected" in out

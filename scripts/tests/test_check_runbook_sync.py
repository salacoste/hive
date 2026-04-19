from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_runbook_sync.py"
SPEC = spec_from_file_location("check_runbook_sync", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
_extract_refs = MODULE._extract_refs


def test_extract_refs_from_mixed_lines() -> None:
    text = """
Run this:
./scripts/install_acceptance_gate_launchd.sh
./scripts/status_acceptance_gate_launchd.sh
./scripts/uninstall_acceptance_gate_launchd.sh
"""
    refs = _extract_refs(text)
    assert "scripts/install_acceptance_gate_launchd.sh" in refs
    assert "scripts/status_acceptance_gate_launchd.sh" in refs
    assert "scripts/uninstall_acceptance_gate_launchd.sh" in refs


def test_extract_refs_from_inline_commands() -> None:
    text = "Use `uv run python scripts/verify_access_stack.sh` and `scripts/check_runtime_parity.sh`."
    refs = _extract_refs(text)
    assert "scripts/verify_access_stack.sh" in refs
    assert "scripts/check_runtime_parity.sh" in refs


def test_extract_refs_deduplicates() -> None:
    text = """
./scripts/acceptance_weekly_maintenance.sh
scripts/acceptance_weekly_maintenance.sh
"""
    refs = _extract_refs(text)
    assert refs.count("scripts/acceptance_weekly_maintenance.sh") == 1

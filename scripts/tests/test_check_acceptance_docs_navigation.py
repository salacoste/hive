from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_acceptance_docs_navigation.py"
SPEC = spec_from_file_location("check_acceptance_docs_navigation", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_docs_navigation_check_passes_for_expected_refs(tmp_path: Path, monkeypatch, capsys) -> None:
    runbook = tmp_path / "runbook.md"
    factory = tmp_path / "factory.md"
    ops = tmp_path / "ops.md"

    runbook.write_text("docs/ops/acceptance-automation-map.md\n", encoding="utf-8")
    factory.write_text("../ops/acceptance-automation-map.md\n", encoding="utf-8")
    ops.write_text(
        "scripts/check_acceptance_gate_toggles_sync.py\n"
        "scripts/check_backlog_archive_index.py\n"
        "scripts/check_acceptance_preset_smoke_determinism.sh\n"
        "scripts/check_acceptance_guardrails_sync.py\n"
        "scripts/check_acceptance_runbook_sanity_sync.py\n"
        "scripts/check_acceptance_self_check_test_bundle_sync.py\n"
        "scripts/check_acceptance_guardrail_marker_set_sync.py\n"
        "scripts/check_backlog_status_consistency.py\n"
        "scripts/check_backlog_status_json_contract.py\n"
        "scripts/check_backlog_status_drift.py\n"
        "scripts/check_backlog_status_artifacts_index.py\n"
        "uv run python scripts/backlog_status_artifact.py\n"
        "uv run python scripts/backlog_status_hygiene.py --keep 50\n"
        "HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true ./scripts/acceptance_toolchain_self_check.sh\n"
        "HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh\n"
        "HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh\n"
        "./scripts/acceptance_toolchain_self_check_deep.sh\n"
        "## Quick Start\n"
        "./scripts/acceptance_gate_presets.sh fast\n"
        "./scripts/acceptance_gate_presets.sh strict\n"
        "./scripts/acceptance_gate_presets.sh full\n"
        "./scripts/acceptance_gate_presets.sh full-deep\n"
        "scripts/check_acceptance_preset_contract_sync.py\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        MODULE,
        "CHECKS",
        [
            (runbook, ["docs/ops/acceptance-automation-map.md"]),
            (factory, ["../ops/acceptance-automation-map.md"]),
            (
                ops,
                [
                    "scripts/check_acceptance_gate_toggles_sync.py",
                    "scripts/check_backlog_archive_index.py",
                    "scripts/check_acceptance_preset_smoke_determinism.sh",
                    "scripts/check_acceptance_guardrails_sync.py",
                    "scripts/check_acceptance_runbook_sanity_sync.py",
                    "scripts/check_acceptance_self_check_test_bundle_sync.py",
                    "scripts/check_acceptance_guardrail_marker_set_sync.py",
                    "scripts/check_backlog_status_consistency.py",
                    "scripts/check_backlog_status_json_contract.py",
                    "scripts/check_backlog_status_drift.py",
                    "scripts/check_backlog_status_artifacts_index.py",
                    "uv run python scripts/backlog_status_artifact.py",
                    "uv run python scripts/backlog_status_hygiene.py --keep 50",
                    "HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true ./scripts/acceptance_toolchain_self_check.sh",
                    "HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh",
                    "HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh",
                    "./scripts/acceptance_toolchain_self_check_deep.sh",
                    "## Quick Start",
                    "./scripts/acceptance_gate_presets.sh fast",
                    "./scripts/acceptance_gate_presets.sh strict",
                    "./scripts/acceptance_gate_presets.sh full",
                    "./scripts/acceptance_gate_presets.sh full-deep",
                    "scripts/check_acceptance_preset_contract_sync.py",
                ],
            ),
        ],
    )
    rc = MODULE.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "[ok] acceptance docs navigation is consistent" in out


def test_docs_navigation_check_fails_when_ref_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    broken = tmp_path / "broken.md"
    broken.write_text("placeholder\n", encoding="utf-8")
    monkeypatch.setattr(MODULE, "CHECKS", [(broken, ["MISSING_TOKEN"])])
    rc = MODULE.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "[fail] missing navigation refs: 1" in out


def test_default_checks_include_required_acceptance_map_markers() -> None:
    checks = dict(MODULE.CHECKS)
    ops_needles = checks[Path("docs/ops/acceptance-automation-map.md")]
    assert "scripts/check_acceptance_gate_toggles_sync.py" in ops_needles
    assert "scripts/check_backlog_archive_index.py" in ops_needles
    assert "scripts/check_acceptance_preset_smoke_determinism.sh" in ops_needles
    assert "scripts/check_acceptance_guardrails_sync.py" in ops_needles
    assert "scripts/check_acceptance_runbook_sanity_sync.py" in ops_needles
    assert "scripts/check_acceptance_self_check_test_bundle_sync.py" in ops_needles
    assert "scripts/check_acceptance_guardrail_marker_set_sync.py" in ops_needles
    assert "scripts/check_backlog_status_consistency.py" in ops_needles
    assert "scripts/check_backlog_status_json_contract.py" in ops_needles
    assert "scripts/check_backlog_status_drift.py" in ops_needles
    assert "scripts/check_backlog_status_artifacts_index.py" in ops_needles
    assert "uv run python scripts/backlog_status_artifact.py" in ops_needles
    assert "uv run python scripts/backlog_status_hygiene.py --keep 50" in ops_needles
    assert "HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true ./scripts/acceptance_toolchain_self_check.sh" in ops_needles
    assert "HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true ./scripts/acceptance_toolchain_self_check.sh" in ops_needles
    assert (
        "HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true "
        "./scripts/acceptance_toolchain_self_check.sh"
    ) in ops_needles
    assert "./scripts/acceptance_toolchain_self_check_deep.sh" in ops_needles
    assert "./scripts/acceptance_gate_presets.sh fast" in ops_needles
    assert "./scripts/acceptance_gate_presets.sh strict" in ops_needles
    assert "./scripts/acceptance_gate_presets.sh full" in ops_needles
    assert "./scripts/acceptance_gate_presets.sh full-deep" in ops_needles
    assert "scripts/check_acceptance_preset_contract_sync.py" in ops_needles

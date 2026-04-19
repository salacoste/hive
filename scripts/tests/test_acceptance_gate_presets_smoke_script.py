from pathlib import Path


def test_presets_smoke_script_uses_clean_env_wrapper() -> None:
    script = Path("scripts/acceptance_gate_presets_smoke.sh").read_text(encoding="utf-8")
    assert "run_clean_preset()" in script
    assert "-u HIVE_ACCEPTANCE_RUN_PRESET_SMOKE" in script
    assert "-u HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE" in script
    assert "-u HIVE_DELIVERY_E2E_SKIP_REAL" in script
    assert "-u HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY" in script
    assert 'run_step "preset full-deep print-only" run_clean_preset full-deep --print-env-only' in script

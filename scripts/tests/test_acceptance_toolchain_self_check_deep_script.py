from pathlib import Path


def test_deep_wrapper_sets_expected_toggles_and_delegates() -> None:
    script = Path("scripts/acceptance_toolchain_self_check_deep.sh").read_text(encoding="utf-8")
    assert 'export HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true' in script
    assert 'export HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true' in script
    assert 'exec ./scripts/acceptance_toolchain_self_check.sh "$@"' in script

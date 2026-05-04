from __future__ import annotations

import os
import subprocess
from pathlib import Path


SCRIPT = Path("scripts/acceptance_gate_presets_smoke.sh")


def _extract_mode_block(output: str, mode: str) -> str:
    blocks = output.split("== Acceptance Gate Preset ==")
    for block in blocks:
        if f"mode={mode}" in block:
            return block
    raise AssertionError(f"mode block not found: {mode}")


def test_presets_smoke_is_deterministic_with_contaminated_env() -> None:
    env = os.environ.copy()
    env["HIVE_ACCEPTANCE_ENFORCE_HISTORY"] = "true"
    env["HIVE_ACCEPTANCE_SUMMARY_JSON"] = "true"
    env["HIVE_ACCEPTANCE_RUN_SELF_CHECK"] = "true"
    env["HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK"] = "true"
    env["HIVE_ACCEPTANCE_RUN_PRESET_SMOKE"] = "true"
    env["HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE"] = "true"
    env["HIVE_DELIVERY_E2E_SKIP_REAL"] = "true"
    env["HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY"] = "true"
    env["HIVE_ACCEPTANCE_SKIP_TELEGRAM"] = "true"

    proc = subprocess.run(
        [str(SCRIPT)],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    out = proc.stdout

    fast_block = _extract_mode_block(out, "fast")
    assert "HIVE_ACCEPTANCE_ENFORCE_HISTORY=" in fast_block
    assert "HIVE_ACCEPTANCE_SUMMARY_JSON=" in fast_block
    assert "HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=" in fast_block
    assert "HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=" in fast_block
    assert "HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET=false" in fast_block
    assert "HIVE_DELIVERY_E2E_SKIP_REAL=" in fast_block
    assert "HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=" in fast_block

    strict_block = _extract_mode_block(out, "strict")
    assert "HIVE_ACCEPTANCE_ENFORCE_HISTORY=true" in strict_block
    assert "HIVE_ACCEPTANCE_RUN_SELF_CHECK=" in strict_block
    assert "HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=" in strict_block
    assert "HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=" in strict_block
    assert "HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET=true" in strict_block
    assert "HIVE_DELIVERY_E2E_SKIP_REAL=" in strict_block

    full_deep_block = _extract_mode_block(out, "full-deep")
    assert "HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=true" in full_deep_block
    assert "HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=true" in full_deep_block
    assert "HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET=true" in full_deep_block
    assert "HIVE_DELIVERY_E2E_SKIP_REAL=true" in full_deep_block
    assert "HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true" in full_deep_block

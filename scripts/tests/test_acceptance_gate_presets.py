from __future__ import annotations

import subprocess
from pathlib import Path


SCRIPT = Path("scripts/acceptance_gate_presets.sh")


def _run(mode: str) -> str:
    proc = subprocess.run(
        [str(SCRIPT), mode, "--print-env-only"],
        check=True,
        text=True,
        capture_output=True,
    )
    return proc.stdout


def _run_with_project(mode: str, project_id: str) -> str:
    proc = subprocess.run(
        [str(SCRIPT), mode, "--project", project_id, "--print-env-only"],
        check=True,
        text=True,
        capture_output=True,
    )
    return proc.stdout


def _extract_value(output: str, key: str) -> str:
    prefix = f"{key}="
    for line in output.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"missing key in output: {key}")


def test_fast_mode_print_only() -> None:
    out = _run("fast")
    assert "mode=fast" in out
    assert "HIVE_ACCEPTANCE_SKIP_CHECKLIST=true" in out
    assert "HIVE_ACCEPTANCE_SKIP_TELEGRAM=true" in out
    assert "[ok] print-only mode, gate execution skipped" in out


def test_strict_mode_print_only() -> None:
    out = _run("strict")
    assert "mode=strict" in out
    assert "HIVE_ACCEPTANCE_ENFORCE_HISTORY=true" in out
    assert "HIVE_ACCEPTANCE_SUMMARY_JSON=true" in out
    assert "[ok] print-only mode, gate execution skipped" in out


def test_full_mode_print_only() -> None:
    out = _run("full")
    assert "mode=full" in out
    assert "HIVE_ACCEPTANCE_RUN_SELF_CHECK=true" in out
    assert "HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK=true" in out
    assert "[ok] print-only mode, gate execution skipped" in out


def test_full_deep_mode_print_only() -> None:
    out = _run("full-deep")
    assert "mode=full-deep" in out
    assert "HIVE_ACCEPTANCE_RUN_SELF_CHECK=true" in out
    assert "HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK=true" in out
    assert "HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=true" in out
    assert "HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=true" in out
    assert "HIVE_DELIVERY_E2E_SKIP_REAL=true" in out
    assert "HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true" in out
    assert "[ok] print-only mode, gate execution skipped" in out


def test_project_scope_override_print_only() -> None:
    out = _run_with_project("fast", "demo-project")
    assert "mode=fast" in out
    assert "HIVE_ACCEPTANCE_PROJECT_ID=demo-project" in out


def test_unknown_mode_exits_non_zero() -> None:
    proc = subprocess.run(
        [str(SCRIPT), "unknown-mode", "--print-env-only"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert "usage:" in proc.stderr


def test_project_without_value_exits_non_zero() -> None:
    proc = subprocess.run(
        [str(SCRIPT), "fast", "--project"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert "--project requires value" in proc.stderr


def test_launcher_handles_empty_filtered_args_under_nounset() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'if [[ "${#filtered_args[@]}" -gt 0 ]]; then' in text
    assert 'exec ./scripts/autonomous_acceptance_gate.sh "${filtered_args[@]}"' in text
    assert "exec ./scripts/autonomous_acceptance_gate.sh" in text


def test_mode_contract_flags_are_stable() -> None:
    fast = _run("fast")
    assert _extract_value(fast, "HIVE_ACCEPTANCE_ENFORCE_HISTORY") == ""
    assert _extract_value(fast, "HIVE_ACCEPTANCE_RUN_SELF_CHECK") == ""
    assert _extract_value(fast, "HIVE_ACCEPTANCE_RUN_PRESET_SMOKE") == ""
    assert _extract_value(fast, "HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE") == ""
    assert _extract_value(fast, "HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET") == "false"
    assert _extract_value(fast, "HIVE_DELIVERY_E2E_SKIP_REAL") == ""

    strict = _run("strict")
    assert _extract_value(strict, "HIVE_ACCEPTANCE_ENFORCE_HISTORY") == "true"
    assert _extract_value(strict, "HIVE_ACCEPTANCE_RUN_SELF_CHECK") == ""
    assert _extract_value(strict, "HIVE_ACCEPTANCE_RUN_PRESET_SMOKE") == ""
    assert _extract_value(strict, "HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE") == ""
    assert _extract_value(strict, "HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET") == "true"
    assert _extract_value(strict, "HIVE_DELIVERY_E2E_SKIP_REAL") == ""

    full = _run("full")
    assert _extract_value(full, "HIVE_ACCEPTANCE_ENFORCE_HISTORY") == "true"
    assert _extract_value(full, "HIVE_ACCEPTANCE_RUN_SELF_CHECK") == "true"
    assert _extract_value(full, "HIVE_ACCEPTANCE_RUN_PRESET_SMOKE") == ""
    assert _extract_value(full, "HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE") == ""
    assert _extract_value(full, "HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET") == "true"
    assert _extract_value(full, "HIVE_DELIVERY_E2E_SKIP_REAL") == ""

    full_deep = _run("full-deep")
    assert _extract_value(full_deep, "HIVE_ACCEPTANCE_ENFORCE_HISTORY") == "true"
    assert _extract_value(full_deep, "HIVE_ACCEPTANCE_RUN_SELF_CHECK") == "true"
    assert _extract_value(full_deep, "HIVE_ACCEPTANCE_RUN_PRESET_SMOKE") == "true"
    assert _extract_value(full_deep, "HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE") == "true"
    assert _extract_value(full_deep, "HIVE_ACCEPTANCE_RUN_MIN_REGRESSION_SET") == "true"
    assert _extract_value(full_deep, "HIVE_DELIVERY_E2E_SKIP_REAL") == "true"
    assert _extract_value(full_deep, "HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY") == "true"

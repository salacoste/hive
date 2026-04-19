import os
import subprocess
from pathlib import Path


def test_operator_profile_daily_mode_includes_operator_safe_health_overrides() -> None:
    script = Path("scripts/autonomous_operator_profile.sh").read_text(encoding="utf-8")
    assert "--mode <daily|deep|dry-run>" in script
    assert "--remediate|--no-remediate" in script
    assert "--no-remediation" in script
    assert "--acceptance-preset <fast|strict|full|full-deep>" in script
    assert '--acceptance-extra-args "<...>"' in script
    assert "--ops-summary-only" in script
    assert "--daily-remediate|--no-daily-remediate" in script
    assert "--deep-remediate|--no-deep-remediate" in script
    assert "--remediate-action <escalated|failed>" in script
    assert "--project-health-profile <prod|strict|relaxed>" in script
    assert "--skip-preflight" in script
    assert "--skip-self-check" in script
    assert 'Acceptance gate (${DAILY_ACCEPTANCE_PRESET} preset, operator-safe health thresholds)' in script
    assert 'HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE="$HEALTH_ALLOW_LOOP_STALE"' in script
    assert 'HIVE_AUTONOMOUS_HEALTH_MAX_STUCK_RUNS="$HEALTH_MAX_STUCK_RUNS"' in script
    assert 'HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS="$HEALTH_MAX_NO_PROGRESS_PROJECTS"' in script
    assert "Stale runs remediation (apply before strict gate)" in script
    assert "HIVE_OPERATOR_AUTO_REMEDIATE_STALE" in script
    assert "HIVE_OPERATOR_PROJECT_HEALTH_PROFILE" in script
    assert "HIVE_OPERATOR_ACCEPTANCE_PRESET" in script
    assert "HIVE_OPERATOR_ACCEPTANCE_EXTRA_ARGS" in script
    assert "HIVE_OPERATOR_REMEDIATE_ACTION" in script
    assert "HIVE_AUTONOMOUS_REMEDIATE_DRY_RUN=false" in script
    assert "HIVE_AUTONOMOUS_REMEDIATE_CONFIRM=true" in script
    assert "run_preflight_if_enabled()" in script
    assert "run_acceptance_gate_with_preset()" in script
    assert "run_acceptance_preset_preview()" in script
    assert "ops-summary-only mode: skipping preflight, deep self-check, remediation, acceptance gate" in script


def test_operator_profile_deep_mode_includes_operator_safe_health_overrides() -> None:
    script = Path("scripts/autonomous_operator_profile.sh").read_text(encoding="utf-8")
    assert 'Acceptance gate (${DEEP_ACCEPTANCE_PRESET} preset, operator-safe health thresholds)' in script
    assert 'HIVE_AUTONOMOUS_HEALTH_ALLOW_LOOP_STALE="$HEALTH_ALLOW_LOOP_STALE"' in script
    assert 'HIVE_AUTONOMOUS_HEALTH_MAX_STUCK_RUNS="$HEALTH_MAX_STUCK_RUNS"' in script
    assert 'HIVE_AUTONOMOUS_HEALTH_MAX_NO_PROGRESS_PROJECTS="$HEALTH_MAX_NO_PROGRESS_PROJECTS"' in script
    assert "HIVE_OPERATOR_DEEP_AUTO_REMEDIATE_STALE" in script
    assert "Stale runs remediation (apply before full-deep gate)" in script
    assert "run_deep_self_check_if_enabled()" in script


def test_operator_profile_cli_remediate_override_sets_effective_flags_true() -> None:
    env = os.environ.copy()
    env["HIVE_OPERATOR_AUTO_REMEDIATE_STALE"] = "false"
    env["HIVE_OPERATOR_DEEP_AUTO_REMEDIATE_STALE"] = "false"
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "deep",
            "--project",
            "demo",
            "--print-plan",
            "--remediate",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    out = proc.stdout
    assert "daily_auto_remediate_stale=true" in out
    assert "deep_auto_remediate_stale=true" in out


def test_operator_profile_cli_no_remediate_override_sets_effective_flags_false() -> None:
    env = os.environ.copy()
    env["HIVE_OPERATOR_AUTO_REMEDIATE_STALE"] = "true"
    env["HIVE_OPERATOR_DEEP_AUTO_REMEDIATE_STALE"] = "true"
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "daily",
            "--project",
            "demo",
            "--print-plan",
            "--no-remediate",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    out = proc.stdout
    assert "daily_auto_remediate_stale=false" in out
    assert "deep_auto_remediate_stale=false" in out


def test_operator_profile_cli_no_remediation_alias_sets_effective_flags_false() -> None:
    env = os.environ.copy()
    env["HIVE_OPERATOR_AUTO_REMEDIATE_STALE"] = "true"
    env["HIVE_OPERATOR_DEEP_AUTO_REMEDIATE_STALE"] = "true"
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "daily",
            "--project",
            "demo",
            "--print-plan",
            "--no-remediation",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    out = proc.stdout
    assert "daily_auto_remediate_stale=false" in out
    assert "deep_auto_remediate_stale=false" in out


def test_operator_profile_cli_remediate_action_override_is_applied() -> None:
    env = os.environ.copy()
    env["HIVE_OPERATOR_REMEDIATE_ACTION"] = "escalated"
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "deep",
            "--project",
            "demo",
            "--print-plan",
            "--remediate-action",
            "failed",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    out = proc.stdout
    assert "remediate_action=failed" in out


def test_operator_profile_cli_rejects_invalid_remediate_action() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "daily",
            "--project",
            "demo",
            "--print-plan",
            "--remediate-action",
            "bogus",
        ],
        check=False,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    assert proc.returncode == 2
    assert "--remediate-action must be one of: escalated, failed" in proc.stderr


def test_operator_profile_mode_specific_overrides_win_over_global_override() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "deep",
            "--project",
            "demo",
            "--print-plan",
            "--remediate",
            "--no-deep-remediate",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    out = proc.stdout
    assert "daily_auto_remediate_stale=true" in out
    assert "deep_auto_remediate_stale=false" in out


def test_operator_profile_daily_specific_override_can_enable_when_global_disabled() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "daily",
            "--project",
            "demo",
            "--print-plan",
            "--no-remediate",
            "--daily-remediate",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    out = proc.stdout
    assert "daily_auto_remediate_stale=true" in out
    assert "deep_auto_remediate_stale=false" in out


def test_operator_profile_project_health_profile_strict_sets_expected_thresholds() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "daily",
            "--project",
            "demo",
            "--print-plan",
            "--project-health-profile",
            "strict",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    out = proc.stdout
    assert "project_health_profile=strict" in out
    assert "health_max_stuck_runs=0" in out
    assert "health_max_no_progress_projects=0" in out
    assert "health_allow_loop_stale=false" in out


def test_operator_profile_project_health_profile_relaxed_sets_expected_thresholds() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "daily",
            "--project",
            "demo",
            "--print-plan",
            "--project-health-profile",
            "relaxed",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    out = proc.stdout
    assert "project_health_profile=relaxed" in out
    assert "health_max_stuck_runs=2" in out
    assert "health_max_no_progress_projects=2" in out
    assert "health_allow_loop_stale=true" in out


def test_operator_profile_rejects_invalid_project_health_profile() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "daily",
            "--project",
            "demo",
            "--print-plan",
            "--project-health-profile",
            "bogus",
        ],
        check=False,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    assert proc.returncode == 2
    assert "--project-health-profile must be one of: prod, strict, relaxed" in proc.stderr


def test_operator_profile_skip_preflight_and_self_check_flags_skip_steps() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "deep",
            "--project",
            "demo",
            "--print-plan",
            "--skip-preflight",
            "--skip-self-check",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    out = proc.stdout
    assert "skip_preflight=true" in out
    assert "skip_self_check=true" in out
    assert "[skip] container preflight (--skip-preflight)" in out
    assert "[skip] deep self-check (--skip-self-check)" in out


def test_operator_profile_skip_self_check_info_for_non_deep_mode() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "daily",
            "--project",
            "demo",
            "--print-plan",
            "--skip-self-check",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    out = proc.stdout
    assert "skip_self_check=true" in out
    assert "[info] --skip-self-check has no effect in mode=daily" in out


def test_operator_profile_ops_summary_only_skips_pipeline_steps() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "deep",
            "--project",
            "demo",
            "--print-plan",
            "--ops-summary-only",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    out = proc.stdout
    assert "ops_summary_only=true" in out
    assert "[info] ops-summary-only mode: skipping preflight, deep self-check, remediation, acceptance gate" in out
    assert "== Ops summary (json) ==" in out
    assert "Container preflight" not in out
    assert "Deep self-check" not in out
    assert "Stale runs remediation" not in out
    assert "Acceptance gate" not in out


def test_operator_profile_acceptance_preset_override_applies_to_daily_gate() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "daily",
            "--project",
            "demo",
            "--print-plan",
            "--acceptance-preset",
            "full",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    out = proc.stdout
    assert "acceptance_preset_daily=full" in out
    assert "acceptance_preset_deep=full" in out
    assert "Acceptance gate (full preset, operator-safe health thresholds)" in out
    assert "./scripts/acceptance_gate_presets.sh full --project demo" in out


def test_operator_profile_acceptance_preset_override_dry_run_previews_only_selected_preset() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "dry-run",
            "--project",
            "demo",
            "--print-plan",
            "--acceptance-preset",
            "fast",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    out = proc.stdout
    assert "Acceptance fast preset (env preview)" in out
    assert "./scripts/acceptance_gate_presets.sh fast --project demo --print-env-only" in out
    assert "Acceptance strict preset (env preview)" not in out
    assert "Acceptance full-deep preset (env preview)" not in out


def test_operator_profile_rejects_invalid_acceptance_preset() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "daily",
            "--project",
            "demo",
            "--print-plan",
            "--acceptance-preset",
            "bogus",
        ],
        check=False,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    assert proc.returncode == 2
    assert "--acceptance-preset must be one of: fast, strict, full, full-deep" in proc.stderr


def test_operator_profile_acceptance_extra_args_are_forwarded_to_gate_command() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "daily",
            "--project",
            "demo",
            "--print-plan",
            "--acceptance-preset",
            "full",
            "--acceptance-extra-args",
            "--summary-json --skip-telegram",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    out = proc.stdout
    assert "acceptance_extra_args_raw=--summary-json --skip-telegram" in out
    assert "acceptance_extra_args_count=2" in out
    assert "./scripts/acceptance_gate_presets.sh full --project demo -- --summary-json --skip-telegram" in out


def test_operator_profile_acceptance_extra_args_are_forwarded_to_dry_run_preview() -> None:
    proc = subprocess.run(
        [
            "./scripts/autonomous_operator_profile.sh",
            "--mode",
            "dry-run",
            "--project",
            "demo",
            "--print-plan",
            "--acceptance-preset",
            "fast",
            "--acceptance-extra-args",
            "--summary-json",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    out = proc.stdout
    assert "./scripts/acceptance_gate_presets.sh fast --project demo --print-env-only -- --summary-json" in out

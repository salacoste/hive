from pathlib import Path


def test_self_check_script_includes_runtime_parity_toggle() -> None:
    script = Path("scripts/acceptance_toolchain_self_check.sh").read_text(encoding="utf-8")
    assert "scripts/acceptance_toolchain_self_check_deep.sh \\" in script
    assert "scripts/acceptance_deep_profile.sh \\" in script
    assert 'run_step "backlog status consistency check" uv run python scripts/check_backlog_status_consistency.py' in script
    assert 'run_step "backlog status json contract check" uv run python scripts/check_backlog_status_json_contract.py' in script
    assert 'run_step "backlog status auto-refresh" sh -lc "uv run python scripts/backlog_status_artifact.py && uv run python scripts/backlog_status_hygiene.py --keep 50"' in script
    assert 'run_step "backlog status drift check" uv run python scripts/check_backlog_status_drift.py' in script
    assert 'run_step "backlog status artifacts index check" uv run python scripts/check_backlog_status_artifacts_index.py' in script
    assert 'run_step "backlog archive index check" uv run python scripts/check_backlog_archive_index.py' in script
    assert "scripts/tests/test_backlog_status.py" in script
    assert "scripts/tests/test_backlog_status_artifact.py" in script
    assert "scripts/tests/test_backlog_status_hygiene.py" in script
    assert "scripts/tests/test_validate_backlog_markdown.py" in script
    assert "scripts/tests/test_acceptance_ops_summary.py" in script
    assert "scripts/tests/test_acceptance_gate_result_artifact.py" in script
    assert "scripts/tests/test_acceptance_weekly_maintenance_script.py" in script
    assert "scripts/tests/test_check_operational_api_contracts.py" in script
    assert "scripts/tests/test_autonomous_scheduler_daemon.py" in script
    assert "scripts/tests/test_check_backlog_status_consistency.py" in script
    assert "scripts/tests/test_check_backlog_status_json_contract.py" in script
    assert "scripts/tests/test_check_backlog_status_drift.py" in script
    assert "scripts/tests/test_check_backlog_status_artifacts_index.py" in script
    assert "scripts/tests/test_check_backlog_archive_index.py" in script
    assert "scripts/tests/test_acceptance_deep_profile_script.py" in script
    assert 'RUN_RUNTIME_PARITY="${HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY:-false}"' in script
    assert 'echo "run_runtime_parity=$RUN_RUNTIME_PARITY"' in script
    assert 'if [[ "$RUN_RUNTIME_PARITY" == "true" ]]; then' in script
    assert 'run_step "runtime parity check" ./scripts/check_runtime_parity.sh' in script
    assert 'echo "[skip] runtime parity check"' in script
    assert 'run_step "python syntax (scheduler daemon)" uv run python -m py_compile scripts/autonomous_scheduler_daemon.py' in script
    assert "scripts/_cron_job_lib.sh \\" in script
    assert "scripts/install_acceptance_gate_cron.sh \\" in script
    assert "scripts/status_acceptance_gate_cron.sh \\" in script
    assert "scripts/uninstall_acceptance_gate_cron.sh \\" in script
    assert "scripts/install_acceptance_weekly_cron.sh \\" in script
    assert "scripts/status_acceptance_weekly_cron.sh \\" in script
    assert "scripts/uninstall_acceptance_weekly_cron.sh \\" in script
    assert "scripts/install_autonomous_loop_cron.sh \\" in script
    assert "scripts/status_autonomous_loop_cron.sh \\" in script
    assert "scripts/uninstall_autonomous_loop_cron.sh" in script
    assert "scripts/autonomous_operator_profile.sh \\" in script

from pathlib import Path


def test_deep_profile_script_contract() -> None:
    script = Path("scripts/acceptance_deep_profile.sh").read_text(encoding="utf-8")
    assert 'PROJECT_ID="${HIVE_ACCEPTANCE_PROJECT_ID:-default}"' in script
    assert "run_ops_command()" in script
    assert './scripts/hive_ops_run.sh "$@"' in script
    assert 'run_step "acceptance gate full-deep preset"' in script
    assert 'run_ops_command env HIVE_ACCEPTANCE_PROJECT_ID="$PROJECT_ID" ./scripts/acceptance_gate_presets.sh full-deep' in script
    assert 'run_step "backlog status artifact refresh"' in script
    assert "scripts/backlog_status_artifact.py --output docs/ops/backlog-status/latest.json" in script
    assert 'run_step "acceptance ops summary (json)"' in script
    assert "scripts/acceptance_ops_summary.py --json" in script

from pathlib import Path


def test_weekly_maintenance_supports_deep_profile_hook() -> None:
    script = Path("scripts/acceptance_weekly_maintenance.sh").read_text(encoding="utf-8")
    assert 'WEEKLY_DEEP_PROFILE="${HIVE_ACCEPTANCE_WEEKLY_DEEP_PROFILE:-false}"' in script
    assert 'WEEKLY_DEEP_PROJECT_ID="${HIVE_ACCEPTANCE_WEEKLY_DEEP_PROJECT_ID:-${HIVE_ACCEPTANCE_PROJECT_ID:-default}}"' in script
    assert "run_ops_command()" in script
    assert 'run_step "weekly deep acceptance profile"' in script
    assert 'run_ops_command ./scripts/acceptance_deep_profile.sh --project "$WEEKLY_DEEP_PROJECT_ID"' in script

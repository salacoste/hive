from pathlib import Path


def test_upstream_sync_regression_gate_supports_smoke_and_full_profiles() -> None:
    script = Path("scripts/upstream_sync_regression_gate.sh").read_text(encoding="utf-8")
    assert 'PROFILE="${HIVE_UPSTREAM_SYNC_GATE_PROFILE:-smoke}"' in script
    assert 'PROJECT_ID="${HIVE_UPSTREAM_SYNC_GATE_PROJECT_ID:-default}"' in script
    assert 'HIVE_UPSTREAM_SYNC_GATE_PROFILE must be smoke or full' in script
    assert "run_ops_command()" in script
    assert 'run_step "acceptance toolchain self-check"' in script
    assert 'run_step "runtime parity" run_ops_command env HIVE_RUNTIME_PARITY_PROJECT_ID="$PROJECT_ID" ./scripts/check_runtime_parity.sh' in script
    assert 'run_step "backlog consistency" run_ops_command uv run --no-project python scripts/check_backlog_status_consistency.py' in script
    assert 'if [[ "$PROFILE" == "full" ]]; then' in script
    assert 'run_step "server api tests"' in script
    assert 'uv run --package framework pytest core/framework/server/tests/test_api.py -q' in script
    assert 'uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q' in script
    assert "core/framework/server/tests/test_api.py" in script
    assert "core/framework/server/tests/test_telegram_bridge.py" in script
    assert "npm --prefix core/frontend run test -- --run" in script
    assert "npm --prefix core/frontend run build" in script

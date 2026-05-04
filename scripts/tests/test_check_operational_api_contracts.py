from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "check_operational_api_contracts.py"
SPEC = spec_from_file_location("check_operational_api_contracts", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_validate_health_contract_ok() -> None:
    ok, detail = MODULE._validate_health_contract(
        {
            "status": "ok",
            "telegram_bridge": {"running": True},
        }
    )
    assert ok is True
    assert detail == "ok"


def test_validate_health_contract_missing_telegram_running() -> None:
    ok, detail = MODULE._validate_health_contract({"status": "ok", "telegram_bridge": {}})
    assert ok is False
    assert detail == "telegram_bridge.running missing"


def test_validate_ops_contract_requires_objects() -> None:
    ok, detail = MODULE._validate_ops_contract(
        {
            "status": "ok",
            "summary": {},
            "alerts": {},
            "loop": {},
        }
    )
    assert ok is True
    assert detail == "ok"

    bad_ok, bad_detail = MODULE._validate_ops_contract({"status": "ok", "summary": {}, "alerts": {}})
    assert bad_ok is False
    assert bad_detail == "missing/invalid 'loop' object"


def test_validate_telegram_contract_requires_running_and_owner() -> None:
    ok, detail = MODULE._validate_telegram_contract(
        {
            "status": "ok",
            "bridge": {
                "enabled": True,
                "running": True,
                "poller_owner": True,
                "poll_conflict_409_count": 0,
                "last_poll_conflict_409_at": None,
                "last_poll_conflict_recover_at": None,
                "last_poll_conflict_recover_result": None,
                "auto_clear_webhook_on_409": True,
                "conflict_recover_cooldown_seconds": 120,
                "conflict_warn_threshold": 3,
                "conflict_warn_window_seconds": 3600,
                "poll_conflict_warning_active": False,
                "last_poll_conflict_age_seconds": None,
            },
        }
    )
    assert ok is True
    assert detail == "ok"

    bad_ok, bad_detail = MODULE._validate_telegram_contract(
        {
            "status": "ok",
            "bridge": {"running": True},
        }
    )
    assert bad_ok is False
    assert bad_detail == "bridge.poller_owner missing"


def test_validate_telegram_contract_allows_disabled_bridge_without_conflict_fields() -> None:
    ok, detail = MODULE._validate_telegram_contract(
        {
            "status": "disabled",
            "bridge": {"enabled": False, "running": False, "poller_owner": False},
        }
    )
    assert ok is True
    assert detail == "ok"


def test_validate_telegram_contract_requires_conflict_fields_when_enabled() -> None:
    ok, detail = MODULE._validate_telegram_contract(
        {
            "status": "ok",
            "bridge": {"enabled": True, "running": True, "poller_owner": True},
        }
    )
    assert ok is False
    assert detail == "bridge.poll_conflict_409_count missing"


def test_validate_llm_queue_contract_requires_queue_and_fallback_shapes() -> None:
    ok, detail = MODULE._validate_llm_queue_contract(
        {
            "status": "ok",
            "queue": {
                "limits": {},
                "backoff": {},
                "sync": {},
                "async": {},
            },
            "fallback": {
                "policy": {},
                "history_limit": 50,
                "recent_attempt_chains": [],
            },
        }
    )
    assert ok is True
    assert detail == "ok"

    bad_ok, bad_detail = MODULE._validate_llm_queue_contract(
        {
            "status": "ok",
            "queue": {"limits": {}, "backoff": {}, "sync": {}},
            "fallback": {"policy": {}, "history_limit": 50, "recent_attempt_chains": []},
        }
    )
    assert bad_ok is False
    assert bad_detail == "queue.async missing/invalid"

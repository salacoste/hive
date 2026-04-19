from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "telegram_operator_signoff.py"
SPEC = spec_from_file_location("telegram_operator_signoff", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_derive_overall_status_contract() -> None:
    assert MODULE._derive_overall_status(machine_ok=True, manual_status="pending") == "pending"
    assert MODULE._derive_overall_status(machine_ok=True, manual_status="pass") == "pass"
    assert MODULE._derive_overall_status(machine_ok=True, manual_status="fail") == "fail"
    assert MODULE._derive_overall_status(machine_ok=False, manual_status="pass") == "fail"


def test_payload_checks_contracts() -> None:
    bridge_ok, _ = MODULE._check_bridge_status(
        {
            "bridge": {
                "enabled": True,
                "poller_owner": True,
                "running": True,
                "startup_status": "running",
            }
        }
    )
    health_ok, _ = MODULE._check_health_payload(
        {"status": "ok", "telegram_bridge": {"running": True, "startup_status": "running"}}
    )
    ops_ok, _ = MODULE._check_ops_payload(
        {
            "status": "ok",
            "summary": {"include_runs": True, "projects_total": 1, "runs_total": 2},
            "projects": {"default": {}},
        }
    )
    assert bridge_ok is True
    assert health_ok is True
    assert ops_ok is True


def test_main_writes_artifacts(monkeypatch, tmp_path, capsys) -> None:
    def _fake_request_json(*, method: str, url: str, payload=None, timeout: int = 20):
        if url.endswith("/api/telegram/bridge/status"):
            return 200, {
                "bridge": {
                    "enabled": True,
                    "poller_owner": True,
                    "running": True,
                    "startup_status": "running",
                }
            }
        if url.endswith("/api/health"):
            return 200, {"status": "ok", "telegram_bridge": {"running": True, "startup_status": "running"}}
        if "/api/autonomous/ops/status?" in url:
            return 200, {"status": "ok", "summary": {"include_runs": True}, "projects": {"demo": {}}}
        if url.endswith("/api/autonomous/ops/remediate-stale"):
            return 200, {"status": "ok", "candidates_total": 0, "selected_total": 0}
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(MODULE, "_request_json", _fake_request_json)

    out_json = tmp_path / "telegram-signoff.json"
    out_md = tmp_path / "telegram-signoff.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "telegram_operator_signoff.py",
            "--base-url",
            "http://example:8787",
            "--project-id",
            "demo",
            "--operator",
            "tester",
            "--manual-status",
            "pending",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
    )
    rc = MODULE.main()
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "pending"
    assert payload["machine_ok"] is True
    assert out_md.exists()
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed["status"] == "pending"

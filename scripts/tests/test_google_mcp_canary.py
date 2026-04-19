from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

MODULE_PATH = Path(__file__).resolve().parents[1] / "google_mcp_canary.py"
SPEC = spec_from_file_location("google_mcp_canary", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_render_md_contains_status_and_checks() -> None:
    md = MODULE._render_md(
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "status": "ok",
            "mode": "read_only",
            "failed": 0,
            "checks": [
                {"tool": "calendar_list_events", "ok": True},
                {"tool": "gmail_list_messages", "ok": False, "error": "boom"},
            ],
        }
    )
    assert "Google MCP Canary Latest" in md
    assert "[OK] `calendar_list_events`" in md
    assert "[FAIL] `gmail_list_messages`: `boom`" in md


def test_main_writes_artifacts(monkeypatch, tmp_path: Path) -> None:
    payload = {
        "checks": [
            {"tool": "calendar_list_events", "ok": True},
            {"tool": "gmail_list_messages", "ok": True},
        ],
        "failed": 0,
    }

    monkeypatch.setattr(MODULE, "_run_smoke", lambda dotenv, write: (0, payload, ""))
    rc = MODULE.main(
        [
            "--dotenv",
            ".env",
            "--artifact-dir",
            str(tmp_path),
        ]
    )
    assert rc == 0

    latest = tmp_path / "latest.json"
    latest_md = tmp_path / "latest.md"
    assert latest.exists()
    assert latest_md.exists()

    doc = json.loads(latest.read_text(encoding="utf-8"))
    assert doc["status"] == "ok"
    assert len(doc["checks"]) == 2

from __future__ import annotations

from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "acceptance_report_digest.py"
SPEC = spec_from_file_location("acceptance_report_digest", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_digest_exports_telegram_conflict_kpis(tmp_path: Path, monkeypatch) -> None:
    reports = tmp_path / "acceptance-reports"
    reports.mkdir(parents=True)
    now = datetime.now().isoformat(timespec="seconds")

    (reports / "acceptance-report-a.json").write_text(
        json.dumps(
            {
                "generated_at": now,
                "health": {"status": "ok"},
                "ops": {"status": "ok", "stuck_runs_total": 0, "no_progress_projects_total": 0},
                "telegram_bridge": {
                    "status": "ok",
                    "poll_conflict_409_count": 2,
                    "poll_conflict_warning_active": False,
                },
            }
        ),
        encoding="utf-8",
    )
    (reports / "acceptance-report-b.json").write_text(
        json.dumps(
            {
                "generated_at": now,
                "health": {"status": "ok"},
                "ops": {"status": "ok", "stuck_runs_total": 0, "no_progress_projects_total": 0},
                "telegram_bridge": {
                    "status": "ok",
                    "poll_conflict_409_count": 7,
                    "poll_conflict_warning_active": True,
                },
            }
        ),
        encoding="utf-8",
    )

    out_json = tmp_path / "digest.json"
    monkeypatch.setattr(MODULE, "OUT_DIR", reports)
    monkeypatch.setattr("sys.argv", ["acceptance_report_digest.py", "--days", "7", "--out-json", str(out_json)])

    rc = MODULE.main()
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["telegram_conflict_warning_records"] == 1
    assert payload["telegram_conflict_max_count"] == 7
    assert payload["recent"]
    assert "telegram_conflicts_409" in payload["recent"][0]
    assert "telegram_conflict_warning" in payload["recent"][0]

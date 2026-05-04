from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).resolve().parents[1] / "acceptance_ops_summary.py"
SPEC = spec_from_file_location("acceptance_ops_summary", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_scheduler_status_parses_not_supported(monkeypatch) -> None:
    script = Path("scripts/status_acceptance_gate_cron.sh")

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="not-supported: crontab not found\n", stderr="")

    monkeypatch.setattr(MODULE.subprocess, "run", _fake_run)
    status = MODULE._scheduler_status(script)
    assert status == "not-supported"


def test_docker_scheduler_status_reports_cli_unavailable(monkeypatch) -> None:
    def _fake_run(*_args, **_kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(MODULE.subprocess, "run", _fake_run)
    status = MODULE._docker_scheduler_status()
    assert status == "unknown-cli-unavailable"


def test_ops_summary_includes_backlog_status_fields(tmp_path: Path, monkeypatch, capsys) -> None:
    reports = tmp_path / "acceptance-reports"
    backlog_dir = tmp_path / "backlog-status"
    reports.mkdir(parents=True)
    backlog_dir.mkdir(parents=True)

    (reports / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-10T00:00:00",
                "health": {"status": "ok"},
                "ops": {"status": "ok", "stuck_runs_total": 0, "no_progress_projects_total": 0},
                "telegram_bridge": {
                    "status": "ok",
                    "poll_conflict_409_count": 1,
                    "last_poll_conflict_409_at": 1700000000.0,
                    "last_poll_conflict_recover_result": "delete_webhook_ok",
                    "poll_conflict_warning_active": False,
                },
            }
        ),
        encoding="utf-8",
    )
    (reports / "digest-latest.json").write_text(
        json.dumps({"window_days": 7, "artifacts_total": 3, "pass": 3, "fail": 0}),
        encoding="utf-8",
    )
    (reports / "gate-latest.json").write_text(
        json.dumps(
            {
                "release_matrix": {
                    "status": "pass",
                    "must_passed": 6,
                    "must_total": 6,
                    "must_failed": 0,
                    "must_missing": 0,
                    "must": {"api health contract": "pass"},
                    "should": {"runtime parity": "pass"},
                    "nice": {"local prod checklist": "pass"},
                }
            }
        ),
        encoding="utf-8",
    )
    (backlog_dir / "latest.json").write_text(
        json.dumps(
            {
                "status": {
                    "tasks_total": 9,
                    "status_counts": {"todo": 1, "in_progress": 1, "blocked": 0, "done": 7, "unknown": 0},
                    "in_progress": [9],
                    "focus_refs": [9],
                }
            }
        ),
        encoding="utf-8",
    )
    (backlog_dir / "backlog-status-20260410-010101.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(MODULE, "REPORTS_DIR", reports)
    monkeypatch.setattr(MODULE, "LATEST_ARTIFACT", reports / "latest.json")
    monkeypatch.setattr(MODULE, "DIGEST_JSON", reports / "digest-latest.json")
    monkeypatch.setattr(MODULE, "GATE_RESULTS_JSON", reports / "gate-latest.json")
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_DIR", backlog_dir)
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_LATEST", backlog_dir / "latest.json")
    monkeypatch.setattr(
        MODULE,
        "_run_backlog_status_json",
        lambda: {
            "tasks_total": 9,
            "status_counts": {"todo": 1, "in_progress": 1, "blocked": 0, "done": 7, "unknown": 0},
            "in_progress": [9],
            "focus_refs": [9],
        },
    )
    monkeypatch.setattr("sys.argv", ["acceptance_ops_summary.py", "--json"])

    rc = MODULE.main()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backlog_status_latest_exists"] is True
    assert payload["backlog_status_artifacts_total"] == 1
    assert payload["backlog_tasks_total"] == 9
    assert payload["backlog_in_progress_total"] == 1
    assert payload["backlog_focus_refs_total"] == 1
    assert payload["backlog_done_total"] == 7
    assert payload["backlog_todo_total"] == 1
    assert payload["backlog_drift_detected"] is False
    assert payload["backlog_drift_reason"] == "in_sync"
    assert "scheduler_acceptance_gate_launchd" in payload
    assert "scheduler_acceptance_gate_cron" in payload
    assert "scheduler_acceptance_weekly_launchd" in payload
    assert "scheduler_acceptance_weekly_cron" in payload
    assert "scheduler_autonomous_loop_launchd" in payload
    assert "scheduler_autonomous_loop_cron" in payload
    assert "scheduler_hive_scheduler_container" in payload
    assert payload["release_matrix_status"] == "pass"
    assert payload["release_matrix_must_passed"] == 6
    assert payload["release_matrix_must_total"] == 6
    assert payload["release_matrix_must_failed"] == 0
    assert payload["release_matrix_must_missing"] == 0
    assert payload["release_matrix_must"] == {"api health contract": "pass"}
    assert payload["release_matrix_should"] == {"runtime parity": "pass"}
    assert payload["release_matrix_nice"] == {"local prod checklist": "pass"}
    assert payload["telegram_poll_conflict_409_count"] == 1
    assert payload["telegram_poll_conflict_warning_active"] is False
    assert payload["warnings"] == []


def test_ops_summary_warns_when_artifacts_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    reports = tmp_path / "acceptance-reports"
    backlog_dir = tmp_path / "backlog-status"
    reports.mkdir(parents=True)
    backlog_dir.mkdir(parents=True)

    monkeypatch.setattr(MODULE, "REPORTS_DIR", reports)
    monkeypatch.setattr(MODULE, "LATEST_ARTIFACT", reports / "latest.json")
    monkeypatch.setattr(MODULE, "DIGEST_JSON", reports / "digest-latest.json")
    monkeypatch.setattr(MODULE, "GATE_RESULTS_JSON", reports / "gate-latest.json")
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_DIR", backlog_dir)
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_LATEST", backlog_dir / "latest.json")
    monkeypatch.setattr(MODULE, "_run_backlog_status_json", lambda: None)
    monkeypatch.setattr("sys.argv", ["acceptance_ops_summary.py"])

    rc = MODULE.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "[warn] summary incomplete" in out


def test_ops_summary_reports_backlog_drift(tmp_path: Path, monkeypatch, capsys) -> None:
    reports = tmp_path / "acceptance-reports"
    backlog_dir = tmp_path / "backlog-status"
    reports.mkdir(parents=True)
    backlog_dir.mkdir(parents=True)

    (reports / "latest.json").write_text(
        json.dumps({"generated_at": "2026-04-10T00:00:00"}),
        encoding="utf-8",
    )
    (reports / "digest-latest.json").write_text(json.dumps({"window_days": 7}), encoding="utf-8")
    (backlog_dir / "latest.json").write_text(
        json.dumps(
            {
                "status": {
                    "tasks_total": 5,
                    "status_counts": {"todo": 0, "in_progress": 1, "blocked": 0, "done": 4, "unknown": 0},
                    "in_progress": [5],
                    "focus_refs": [5],
                }
            }
        ),
        encoding="utf-8",
    )
    (backlog_dir / "backlog-status-20260410-010101.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(MODULE, "REPORTS_DIR", reports)
    monkeypatch.setattr(MODULE, "LATEST_ARTIFACT", reports / "latest.json")
    monkeypatch.setattr(MODULE, "DIGEST_JSON", reports / "digest-latest.json")
    monkeypatch.setattr(MODULE, "GATE_RESULTS_JSON", reports / "gate-latest.json")
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_DIR", backlog_dir)
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_LATEST", backlog_dir / "latest.json")
    monkeypatch.setattr(
        MODULE,
        "_run_backlog_status_json",
        lambda: {
            "tasks_total": 6,
            "status_counts": {"todo": 1, "in_progress": 1, "blocked": 0, "done": 4, "unknown": 0},
            "in_progress": [6],
            "focus_refs": [6],
        },
    )
    monkeypatch.setattr("sys.argv", ["acceptance_ops_summary.py", "--json"])

    rc = MODULE.main()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backlog_drift_detected"] is True
    assert payload["backlog_drift_reason"] == "live_vs_artifact_mismatch"


def test_ops_summary_emits_telegram_conflict_soft_warning(tmp_path: Path, monkeypatch, capsys) -> None:
    reports = tmp_path / "acceptance-reports"
    backlog_dir = tmp_path / "backlog-status"
    reports.mkdir(parents=True)
    backlog_dir.mkdir(parents=True)

    (reports / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-10T00:00:00",
                "telegram_bridge": {
                    "status": "ok",
                    "poll_conflict_409_count": 9,
                    "last_poll_conflict_409_at": 1700000000.0,
                    "last_poll_conflict_recover_result": "cooldown",
                    "poll_conflict_warning_active": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (reports / "digest-latest.json").write_text(json.dumps({"window_days": 7}), encoding="utf-8")

    monkeypatch.setattr(MODULE, "REPORTS_DIR", reports)
    monkeypatch.setattr(MODULE, "LATEST_ARTIFACT", reports / "latest.json")
    monkeypatch.setattr(MODULE, "DIGEST_JSON", reports / "digest-latest.json")
    monkeypatch.setattr(MODULE, "GATE_RESULTS_JSON", reports / "gate-latest.json")
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_DIR", backlog_dir)
    monkeypatch.setattr(MODULE, "BACKLOG_STATUS_LATEST", backlog_dir / "latest.json")
    monkeypatch.setattr(MODULE, "_run_backlog_status_json", lambda: None)
    monkeypatch.setattr("sys.argv", ["acceptance_ops_summary.py", "--json"])

    rc = MODULE.main()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["telegram_poll_conflict_warning_active"] is True
    assert payload["telegram_poll_conflict_warning_reason"] == "telegram_409_conflicts_rising"
    assert payload["warnings"] == ["telegram_409_conflicts_rising"]

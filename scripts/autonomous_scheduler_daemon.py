#!/usr/bin/env python3
"""Container-native scheduler for autonomous loop and lightweight acceptance probes."""

from __future__ import annotations

import json
import os
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _parse_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(name: str, default: int, minimum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be integer >= {minimum}, got: {raw!r}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got: {value}")
    return value


def _split_csv(raw: str) -> list[str]:
    if not raw.strip():
        return []
    out: list[str] = []
    for chunk in raw.split(","):
        item = chunk.strip()
        if item:
            out.append(item)
    return out


@dataclass
class SchedulerConfig:
    base_url: str
    autonomous_enabled: bool
    autonomous_interval_seconds: int
    autonomous_auto_start: bool
    autonomous_max_steps_per_project: int
    autonomous_project_ids: list[str]
    acceptance_enabled: bool
    acceptance_interval_seconds: int
    acceptance_project_id: str
    request_timeout_seconds: int
    state_path: str
    heartbeat_interval_seconds: int
    session_id: str
    session_id_by_project: dict[str, str]


def _load_config() -> SchedulerConfig:
    base_url = os.environ.get("HIVE_BASE_URL", "http://hive-core:8787").rstrip("/")
    project_ids = _split_csv(os.environ.get("HIVE_SCHEDULER_PROJECT_IDS", ""))
    session_id = os.environ.get("HIVE_SCHEDULER_SESSION_ID", "").strip()
    session_map_raw = os.environ.get("HIVE_SCHEDULER_SESSION_ID_BY_PROJECT_JSON", "").strip()
    session_map: dict[str, str] = {}
    if session_map_raw:
        try:
            parsed = json.loads(session_map_raw)
        except json.JSONDecodeError as exc:
            raise ValueError("HIVE_SCHEDULER_SESSION_ID_BY_PROJECT_JSON must be valid JSON object") from exc
        if not isinstance(parsed, dict):
            raise ValueError("HIVE_SCHEDULER_SESSION_ID_BY_PROJECT_JSON must be JSON object")
        for key, value in parsed.items():
            k = str(key).strip()
            v = str(value).strip()
            if k and v:
                session_map[k] = v
    return SchedulerConfig(
        base_url=base_url,
        autonomous_enabled=_parse_bool("HIVE_SCHEDULER_AUTONOMOUS_ENABLED", True),
        autonomous_interval_seconds=_parse_int("HIVE_SCHEDULER_AUTONOMOUS_INTERVAL_SECONDS", 120, 10),
        autonomous_auto_start=_parse_bool("HIVE_SCHEDULER_AUTO_START", True),
        autonomous_max_steps_per_project=_parse_int("HIVE_SCHEDULER_MAX_STEPS_PER_PROJECT", 3, 1),
        autonomous_project_ids=project_ids,
        acceptance_enabled=_parse_bool("HIVE_SCHEDULER_ACCEPTANCE_ENABLED", True),
        acceptance_interval_seconds=_parse_int("HIVE_SCHEDULER_ACCEPTANCE_INTERVAL_SECONDS", 3600, 60),
        acceptance_project_id=os.environ.get("HIVE_SCHEDULER_ACCEPTANCE_PROJECT_ID", "default").strip() or "default",
        request_timeout_seconds=_parse_int("HIVE_SCHEDULER_REQUEST_TIMEOUT_SECONDS", 20, 2),
        state_path=os.environ.get("HIVE_SCHEDULER_STATE_PATH", "/tmp/hive_scheduler_state.json"),
        heartbeat_interval_seconds=_parse_int("HIVE_SCHEDULER_HEARTBEAT_INTERVAL_SECONDS", 5, 1),
        session_id=session_id,
        session_id_by_project=session_map,
    )


def _http_post_json(url: str, payload: dict[str, Any], timeout_sec: int) -> tuple[int, dict[str, Any] | None, str | None]:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return int(resp.status), None, "invalid_json_response"
            return int(resp.status), parsed, None
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), None, f"http_error:{text[:300]}"
    except urllib.error.URLError as exc:
        return 0, None, f"url_error:{exc.reason}"
    except Exception as exc:  # pragma: no cover
        return 0, None, f"unexpected_error:{exc}"


def _http_get_json(url: str, timeout_sec: int) -> tuple[int, dict[str, Any] | None, str | None]:
    req = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return int(resp.status), None, "invalid_json_response"
            return int(resp.status), parsed, None
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), None, f"http_error:{text[:300]}"
    except urllib.error.URLError as exc:
        return 0, None, f"url_error:{exc.reason}"
    except Exception as exc:  # pragma: no cover
        return 0, None, f"unexpected_error:{exc}"


def _build_run_cycle_payload(cfg: SchedulerConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "auto_start": cfg.autonomous_auto_start,
        "max_steps_per_project": cfg.autonomous_max_steps_per_project,
    }
    if cfg.autonomous_project_ids:
        payload["project_ids"] = cfg.autonomous_project_ids
    if cfg.session_id_by_project:
        payload["session_id_by_project"] = cfg.session_id_by_project
    elif cfg.session_id:
        payload["session_id"] = cfg.session_id
    return payload


def _log(event: str, **fields: Any) -> None:
    payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **fields}
    print(json.dumps(payload, ensure_ascii=True), flush=True)


def _write_state(path: str, payload: dict[str, Any]) -> None:
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True)
    except Exception:
        return


def _run_autonomous_tick(cfg: SchedulerConfig) -> dict[str, Any]:
    url = f"{cfg.base_url}/api/autonomous/loop/run-cycle/report"
    status, payload, err = _http_post_json(url, _build_run_cycle_payload(cfg), timeout_sec=cfg.request_timeout_seconds)
    if err:
        _log("autonomous_tick_failed", status=status, error=err)
        return {"ok": False, "status": status, "error": err}
    summary = (payload or {}).get("summary") or {}
    out = {
        "ok": True,
        "status": status,
        "projects_total": len((payload or {}).get("projects") or []),
        "completed": int(summary.get("completed", 0) or 0),
        "failed": int(summary.get("failed", 0) or 0),
        "escalated": int(summary.get("escalated", 0) or 0),
        "manual_deferred": int(summary.get("manual_deferred", 0) or 0),
        "in_progress": int(summary.get("in_progress", 0) or 0),
        "idle": int(summary.get("idle", 0) or 0),
    }
    _log(
        "autonomous_tick_ok",
        status=out["status"],
        projects_total=out["projects_total"],
        completed=out["completed"],
        failed=out["failed"],
        escalated=out["escalated"],
        manual_deferred=out["manual_deferred"],
        in_progress=out["in_progress"],
        idle=out["idle"],
    )
    return out


def _run_acceptance_probe(cfg: SchedulerConfig) -> dict[str, Any]:
    health_url = f"{cfg.base_url}/api/health"
    ops_qs = urllib.parse.urlencode({"project_id": cfg.acceptance_project_id, "include_runs": "true"})
    ops_url = f"{cfg.base_url}/api/autonomous/ops/status?{ops_qs}"
    h_status, h_payload, h_err = _http_get_json(health_url, timeout_sec=cfg.request_timeout_seconds)
    o_status, o_payload, o_err = _http_get_json(ops_url, timeout_sec=cfg.request_timeout_seconds)
    if h_err or o_err:
        _log(
            "acceptance_probe_failed",
            health_status=h_status,
            health_error=h_err,
            ops_status=o_status,
            ops_error=o_err,
        )
        return {"ok": False, "health_status": h_status, "ops_status": o_status, "health_error": h_err, "ops_error": o_err}
    alerts = ((o_payload or {}).get("summary") or {}).get("alerts") or {}
    out = {
        "ok": True,
        "health_status": h_status,
        "core_status": (h_payload or {}).get("status"),
        "ops_status": o_status,
        "stuck_runs": int(alerts.get("stuck_runs", 0) or 0),
        "no_progress_projects": int(alerts.get("no_progress_projects", 0) or 0),
    }
    _log(
        "acceptance_probe_ok",
        health_status=out["health_status"],
        core_status=out["core_status"],
        ops_status=out["ops_status"],
        stuck_runs=out["stuck_runs"],
        no_progress_projects=out["no_progress_projects"],
    )
    return out


def main() -> int:
    try:
        cfg = _load_config()
    except ValueError as exc:
        print(f"[fatal] invalid scheduler config: {exc}", file=sys.stderr)
        return 2

    stop = {"value": False}

    def _sigterm(_signum: int, _frame: Any) -> None:
        stop["value"] = True
        _log("scheduler_stop_signal")

    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    _log(
        "scheduler_started",
        base_url=cfg.base_url,
        autonomous_enabled=cfg.autonomous_enabled,
        autonomous_interval_seconds=cfg.autonomous_interval_seconds,
        acceptance_enabled=cfg.acceptance_enabled,
        acceptance_interval_seconds=cfg.acceptance_interval_seconds,
        project_ids=cfg.autonomous_project_ids,
        session_id_bound=bool(cfg.session_id),
        session_map_projects=sorted(cfg.session_id_by_project.keys()),
    )

    now = time.time()
    next_autonomous_at = now
    next_acceptance_at = now
    state: dict[str, Any] = {
        "status": "running",
        "started_at": now,
        "updated_at": now,
        "config": {
            "base_url": cfg.base_url,
            "autonomous_interval_seconds": cfg.autonomous_interval_seconds,
            "acceptance_interval_seconds": cfg.acceptance_interval_seconds,
            "project_ids": cfg.autonomous_project_ids,
        },
        "counters": {
            "autonomous_ok": 0,
            "autonomous_failed": 0,
            "acceptance_ok": 0,
            "acceptance_failed": 0,
        },
    }
    _write_state(cfg.state_path, state)
    last_heartbeat_write = now

    while not stop["value"]:
        now = time.time()
        if cfg.autonomous_enabled and now >= next_autonomous_at:
            res = _run_autonomous_tick(cfg)
            state["last_autonomous_run"] = {"at": now, **res}
            if res.get("ok"):
                state["counters"]["autonomous_ok"] = int(state["counters"]["autonomous_ok"]) + 1
            else:
                state["counters"]["autonomous_failed"] = int(state["counters"]["autonomous_failed"]) + 1
            next_autonomous_at = now + cfg.autonomous_interval_seconds
        if cfg.acceptance_enabled and now >= next_acceptance_at:
            res = _run_acceptance_probe(cfg)
            state["last_acceptance_probe"] = {"at": now, **res}
            if res.get("ok"):
                state["counters"]["acceptance_ok"] = int(state["counters"]["acceptance_ok"]) + 1
            else:
                state["counters"]["acceptance_failed"] = int(state["counters"]["acceptance_failed"]) + 1
            next_acceptance_at = now + cfg.acceptance_interval_seconds
        if now - last_heartbeat_write >= cfg.heartbeat_interval_seconds:
            state["updated_at"] = now
            _write_state(cfg.state_path, state)
            last_heartbeat_write = now
        time.sleep(1.0)

    state["status"] = "stopped"
    state["updated_at"] = time.time()
    _write_state(cfg.state_path, state)
    _log("scheduler_stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

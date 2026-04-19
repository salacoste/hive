"""Project KPI aggregation from persisted Hive session artifacts."""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from framework.server.session_manager import SessionManager


def _parse_timestamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _collect_message_counts(session_dir: Path) -> tuple[int, int]:
    user_count = 0
    total_count = 0
    convs_dir = session_dir / "conversations"
    if not convs_dir.exists():
        return user_count, total_count

    def _scan(parts_dir: Path) -> None:
        nonlocal user_count, total_count
        if not parts_dir.exists():
            return
        for part_file in parts_dir.glob("*.json"):
            try:
                msg = json.loads(part_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if msg.get("is_transition_marker"):
                continue
            if msg.get("role") == "tool":
                continue
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                continue
            total_count += 1
            if msg.get("role") == "user":
                user_count += 1

    _scan(convs_dir / "parts")
    for node_dir in convs_dir.iterdir():
        if not node_dir.is_dir() or node_dir.name == "parts":
            continue
        _scan(node_dir / "parts")

    return user_count, total_count


def compute_project_metrics(*, project_id: str, active_sessions: int) -> dict[str, Any]:
    """Compute project KPIs from on-disk sessions and live counters."""
    sessions = [s for s in SessionManager.list_cold_sessions() if s.get("project_id") == project_id]
    session_ids = [str(s.get("session_id")) for s in sessions if s.get("session_id")]

    total_messages = 0
    user_messages = 0
    completed_executions = 0
    failed_executions = 0
    cycle_times: list[float] = []

    for sid in session_ids:
        session_dir = Path.home() / ".hive" / "queen" / "session" / sid
        u_count, t_count = _collect_message_counts(session_dir)
        user_messages += u_count
        total_messages += t_count

        events_path = session_dir / "events.jsonl"
        if not events_path.exists():
            continue
        exec_windows: dict[str, tuple[datetime, datetime]] = {}
        try:
            with open(events_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    evt_type = str(evt.get("type") or "")
                    exec_id = str(evt.get("execution_id") or "")
                    ts = _parse_timestamp(evt.get("timestamp"))
                    if exec_id and ts is not None:
                        if exec_id in exec_windows:
                            start, end = exec_windows[exec_id]
                            if ts < start:
                                start = ts
                            if ts > end:
                                end = ts
                            exec_windows[exec_id] = (start, end)
                        else:
                            exec_windows[exec_id] = (ts, ts)
                    if evt_type == "execution_completed":
                        completed_executions += 1
                    elif evt_type == "execution_failed":
                        failed_executions += 1
        except OSError:
            continue

        for start, end in exec_windows.values():
            delta = (end - start).total_seconds()
            if delta >= 0:
                cycle_times.append(delta)

    exec_total = completed_executions + failed_executions
    success_rate = (completed_executions / exec_total) if exec_total > 0 else None
    intervention_ratio = (user_messages / total_messages) if total_messages > 0 else 0.0

    return {
        "project_id": project_id,
        "summary": {
            "active_sessions": active_sessions,
            "historical_sessions": len(session_ids),
            "executions_total": exec_total,
            "messages_total": total_messages,
            "user_messages_total": user_messages,
        },
        "kpis": {
            "success_rate": success_rate,
            "cycle_time_seconds_p50": statistics.median(cycle_times) if cycle_times else None,
            "cycle_time_seconds_avg": (sum(cycle_times) / len(cycle_times)) if cycle_times else None,
            "intervention_ratio": intervention_ratio,
        },
    }

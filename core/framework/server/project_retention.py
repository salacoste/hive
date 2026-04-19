"""Per-project retention planning and archive helpers."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from framework.server.session_manager import SessionManager

DEFAULT_RETENTION_POLICY = {
    "history_days": 30,
    "min_sessions_to_keep": 20,
    "archive_enabled": True,
    "archive_root": str(Path.home() / ".hive" / "queen" / "archive"),
}


def normalize_retention_policy(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("retention_policy must be an object")

    out: dict[str, Any] = {}
    if "history_days" in value:
        raw = value.get("history_days")
        if raw is None or raw == "":
            out["history_days"] = None
        else:
            try:
                parsed = int(raw)
            except (TypeError, ValueError):
                raise ValueError("history_days must be an integer >= 1")
            if parsed < 1:
                raise ValueError("history_days must be an integer >= 1")
            out["history_days"] = parsed

    if "min_sessions_to_keep" in value:
        raw = value.get("min_sessions_to_keep")
        if raw is None or raw == "":
            out["min_sessions_to_keep"] = None
        else:
            try:
                parsed = int(raw)
            except (TypeError, ValueError):
                raise ValueError("min_sessions_to_keep must be an integer >= 0")
            if parsed < 0:
                raise ValueError("min_sessions_to_keep must be an integer >= 0")
            out["min_sessions_to_keep"] = parsed

    if "archive_enabled" in value:
        out["archive_enabled"] = bool(value.get("archive_enabled"))

    if "archive_root" in value:
        raw = str(value.get("archive_root") or "").strip()
        out["archive_root"] = raw or None

    return out


def resolve_retention_policy(project: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(DEFAULT_RETENTION_POLICY)
    overrides = project.get("retention_policy") if isinstance(project.get("retention_policy"), dict) else {}
    for key in ("history_days", "min_sessions_to_keep", "archive_enabled", "archive_root"):
        if key in overrides and overrides[key] is not None:
            resolved[key] = overrides[key]
    return {
        "project_id": project.get("id"),
        "defaults": dict(DEFAULT_RETENTION_POLICY),
        "overrides": overrides,
        "effective": resolved,
    }


def build_retention_plan(
    *,
    project_id: str,
    history_days: int,
    min_sessions_to_keep: int,
    live_session_ids: set[str],
    now: float | None = None,
) -> dict[str, Any]:
    now_ts = now or time.time()
    cutoff = now_ts - (history_days * 86400)
    sessions = [s for s in SessionManager.list_cold_sessions() if s.get("project_id") == project_id]
    sessions.sort(key=lambda s: float(s.get("created_at") or 0), reverse=True)

    keep_ids = {str(s.get("session_id")) for s in sessions[:max(0, min_sessions_to_keep)] if s.get("session_id")}
    candidates: list[dict[str, Any]] = []
    for item in sessions:
        sid = str(item.get("session_id") or "")
        if not sid:
            continue
        created_at = float(item.get("created_at") or 0)
        if sid in live_session_ids:
            continue
        if sid in keep_ids:
            continue
        if created_at > cutoff:
            continue
        candidates.append(
            {
                "session_id": sid,
                "created_at": created_at,
                "age_days": max(0.0, (now_ts - created_at) / 86400),
            }
        )

    return {
        "project_id": project_id,
        "historical_sessions": len(sessions),
        "eligible_count": len(candidates),
        "cutoff_timestamp": cutoff,
        "candidates": candidates,
    }


def apply_retention_plan(
    *,
    project_id: str,
    candidates: list[dict[str, Any]],
    archive_enabled: bool,
    archive_root: str,
) -> dict[str, Any]:
    archived: list[str] = []
    deleted: list[str] = []
    skipped: list[dict[str, str]] = []
    base_sessions = Path.home() / ".hive" / "queen" / "session"
    archive_base = Path(archive_root).expanduser().resolve()

    for item in candidates:
        sid = str(item.get("session_id") or "")
        if not sid:
            continue
        src = base_sessions / sid
        if not src.exists():
            skipped.append({"session_id": sid, "reason": "source missing"})
            continue
        try:
            if archive_enabled:
                dest_dir = archive_base / project_id
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / sid
                if dest.exists():
                    dest = dest_dir / f"{sid}-{int(time.time())}"
                shutil.move(str(src), str(dest))
                archived.append(sid)
            else:
                shutil.rmtree(src)
                deleted.append(sid)
        except OSError as e:
            skipped.append({"session_id": sid, "reason": str(e)})

    return {
        "project_id": project_id,
        "archive_enabled": archive_enabled,
        "archive_root": str(archive_base),
        "archived": archived,
        "deleted": deleted,
        "skipped": skipped,
    }

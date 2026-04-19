"""Shared Google token helpers for tools."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_TOKEN_EXPIRY_SKEW_SECONDS = 120
DEFAULT_REQUEST_TIMEOUT_SECONDS = 20
_REFRESH_LOCK = threading.Lock()


def _safe_int(value: str | int | float | None) -> int | None:
    if value is None:
        return None
    try:
        num = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return num if num > 0 else None


def _read_token_file(path: str) -> str | None:
    try:
        token = Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return token or None


def _read_expires_at_for_file(token_file: str) -> int | None:
    default_meta = f"{token_file}.meta.json"
    meta_file = os.getenv("GOOGLE_ACCESS_TOKEN_META_FILE", default_meta).strip() or default_meta
    try:
        raw = Path(meta_file).read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return None
    return _safe_int(payload.get("expires_at"))


def _token_is_fresh(expires_at: int | None) -> bool:
    if expires_at is None:
        # Unknown expiry: defer to caller/API-level errors.
        return True
    skew = int(
        os.getenv("GOOGLE_TOKEN_EXPIRY_SKEW_SECONDS", str(DEFAULT_TOKEN_EXPIRY_SKEW_SECONDS))
        or DEFAULT_TOKEN_EXPIRY_SKEW_SECONDS
    )
    return int(time.time()) < (expires_at - max(skew, 0))


def _refresh_access_token() -> tuple[str, int, str | None] | None:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "").strip()
    if not client_id or not client_secret or not refresh_token:
        return None

    payload = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    timeout = float(
        os.getenv("GOOGLE_REFRESH_REQUEST_TIMEOUT_SECONDS", str(DEFAULT_REQUEST_TIMEOUT_SECONDS))
        or DEFAULT_REQUEST_TIMEOUT_SECONDS
    )
    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Google token refresh failed: %s", exc)
        return None

    access_token = str(data.get("access_token") or "").strip()
    expires_in = _safe_int(data.get("expires_in")) or 0
    scope = str(data.get("scope") or "").strip() or None
    if not access_token:
        logger.warning("Google token refresh returned no access_token")
        return None
    expires_at = int(time.time()) + expires_in if expires_in > 0 else 0
    return access_token, expires_at, scope


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _persist_refreshed_token(
    access_token: str,
    expires_at: int,
    scope: str | None,
    token_file: str,
) -> None:
    os.environ["GOOGLE_ACCESS_TOKEN"] = access_token
    if expires_at > 0:
        os.environ["GOOGLE_TOKEN_EXPIRES_AT"] = str(expires_at)
    if scope:
        os.environ["GOOGLE_OAUTH_SCOPES"] = scope

    if token_file:
        try:
            _atomic_write(Path(token_file), access_token + "\n")
        except Exception as exc:
            logger.warning("Failed to update GOOGLE_ACCESS_TOKEN_FILE: %s", exc)

        meta_file = os.getenv("GOOGLE_ACCESS_TOKEN_META_FILE", f"{token_file}.meta.json").strip()
        if meta_file:
            payload = {"expires_at": expires_at, "updated_at": int(time.time())}
            try:
                _atomic_write(Path(meta_file), json.dumps(payload, ensure_ascii=True) + "\n")
            except Exception as exc:
                logger.warning("Failed to update GOOGLE_ACCESS_TOKEN_META_FILE: %s", exc)


def get_google_access_token_from_env_or_file() -> str | None:
    """Return Google access token from file override or env variable.

    Priority:
    1. GOOGLE_ACCESS_TOKEN_FILE (read on each call)
    2. GOOGLE_ACCESS_TOKEN (process env)

    If token expiry metadata indicates the token is stale and refresh credentials
    are configured, this function auto-refreshes and updates runtime stores.
    """
    token_file = os.getenv("GOOGLE_ACCESS_TOKEN_FILE", "").strip()
    file_token = _read_token_file(token_file) if token_file else None
    env_token = os.getenv("GOOGLE_ACCESS_TOKEN", "").strip() or None

    token_source = "file" if file_token else "env"
    token = file_token or env_token
    if not token:
        return None

    expires_at: int | None
    if token_source == "file" and token_file:
        expires_at = _read_expires_at_for_file(token_file)
    else:
        expires_at = _safe_int(os.getenv("GOOGLE_TOKEN_EXPIRES_AT", "").strip())

    if _token_is_fresh(expires_at):
        return token

    with _REFRESH_LOCK:
        # Re-check after acquiring lock in case another caller refreshed first.
        file_token = _read_token_file(token_file) if token_file else None
        env_token = os.getenv("GOOGLE_ACCESS_TOKEN", "").strip() or None
        token_source = "file" if file_token else "env"
        token = file_token or env_token
        if not token:
            return None

        if token_source == "file" and token_file:
            expires_at = _read_expires_at_for_file(token_file)
        else:
            expires_at = _safe_int(os.getenv("GOOGLE_TOKEN_EXPIRES_AT", "").strip())
        if _token_is_fresh(expires_at):
            return token

        refreshed = _refresh_access_token()
        if refreshed is None:
            return token
        access_token, refreshed_expires_at, scope = refreshed
        _persist_refreshed_token(
            access_token=access_token,
            expires_at=refreshed_expires_at,
            scope=scope,
            token_file=token_file,
        )
        return access_token

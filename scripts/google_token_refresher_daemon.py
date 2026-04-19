#!/usr/bin/env python3
"""Container-native Google token refresher.

Refreshes GOOGLE_ACCESS_TOKEN using GOOGLE_REFRESH_TOKEN on an interval and writes
the latest token to GOOGLE_ACCESS_TOKEN_FILE. Tools can read token from file
without restarting hive-core.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
TELEGRAM_API_BASE = "https://api.telegram.org"
DEFAULT_STATE_PATH = "/data/storage/secrets/google_refresh_state.json"
DEFAULT_ALERT_THRESHOLD = 3
DEFAULT_ALERT_COOLDOWN_SECONDS = 3600


def _desired_uid_gid() -> tuple[int | None, int | None]:
    uid_raw = os.getenv("GOOGLE_TOKEN_FILE_UID", "1001").strip()
    gid_raw = os.getenv("GOOGLE_TOKEN_FILE_GID", "1001").strip()
    try:
        uid = int(uid_raw) if uid_raw else None
    except ValueError:
        uid = None
    try:
        gid = int(gid_raw) if gid_raw else None
    except ValueError:
        gid = None
    return uid, gid


def _chown_if_possible(path: Path, uid: int | None, gid: int | None) -> None:
    if uid is None and gid is None:
        return
    try:
        os.chown(path, uid if uid is not None else -1, gid if gid is not None else -1)
    except Exception:
        # Best-effort ownership alignment; keep writing even if chown is unavailable.
        return


def _refresh_token(client_id: str, client_secret: str, refresh_token: str) -> tuple[str, int]:
    payload = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    token = str(data.get("access_token") or "")
    expires_in = int(data.get("expires_in") or 0)
    if not token:
        raise RuntimeError(f"Missing access_token in response: {data}")
    return token, expires_in


def _parse_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(int(default))).strip().lower()
    return raw in {"1", "true", "yes", "on", "y"}


def _parse_positive_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        val = int(raw)
    except ValueError:
        return max(default, minimum)
    return max(val, minimum)


def _split_chat_ids(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _resolve_alert_chat_ids_raw() -> str:
    return (
        os.getenv("GOOGLE_REFRESH_ALERT_CHAT_IDS", "").strip()
        or os.getenv("GOOGLE_REFRESH_ALERT_CHAT_ID", "").strip()
        or os.getenv("HIVE_TELEGRAM_TEST_CHAT_ID", "").strip()
    )


def _load_state(path: Path) -> dict[str, int | str]:
    if not path.exists():
        return {
            "consecutive_failures": 0,
            "total_failures": 0,
            "total_success": 0,
            "last_success_at": 0,
            "last_failure_at": 0,
            "last_alert_at": 0,
            "last_expires_at": 0,
            "last_error": "",
            "last_alert_status": "",
            "updated_at": 0,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "consecutive_failures": 0,
            "total_failures": 0,
            "total_success": 0,
            "last_success_at": 0,
            "last_failure_at": 0,
            "last_alert_at": 0,
            "last_expires_at": 0,
            "last_error": "",
            "last_alert_status": "state_parse_failed",
            "updated_at": 0,
        }
    return {
        "consecutive_failures": int(payload.get("consecutive_failures") or 0),
        "total_failures": int(payload.get("total_failures") or 0),
        "total_success": int(payload.get("total_success") or 0),
        "last_success_at": int(payload.get("last_success_at") or 0),
        "last_failure_at": int(payload.get("last_failure_at") or 0),
        "last_alert_at": int(payload.get("last_alert_at") or 0),
        "last_expires_at": int(payload.get("last_expires_at") or 0),
        "last_error": str(payload.get("last_error") or ""),
        "last_alert_status": str(payload.get("last_alert_status") or ""),
        "updated_at": int(payload.get("updated_at") or 0),
    }


def _atomic_write(path: Path, content: str) -> None:
    uid, gid = _desired_uid_gid()
    path.parent.mkdir(parents=True, exist_ok=True)
    _chown_if_possible(path.parent, uid, gid)
    try:
        os.chmod(path.parent, 0o775)
    except Exception:
        pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.chmod(tmp, 0o664)
    _chown_if_possible(tmp, uid, gid)
    tmp.replace(path)
    os.chmod(path, 0o664)
    _chown_if_possible(path, uid, gid)


def _save_state(path: Path, state: dict[str, int | str]) -> None:
    _atomic_write(path, json.dumps(state, ensure_ascii=True) + "\n")


def _should_send_alert(
    *,
    consecutive_failures: int,
    threshold: int,
    last_alert_at: int,
    cooldown_seconds: int,
    now: int,
) -> bool:
    if consecutive_failures < threshold:
        return False
    if last_alert_at <= 0:
        return True
    return (now - last_alert_at) >= cooldown_seconds


def _truncate(text: str, max_len: int = 240) -> str:
    text = text.strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _send_telegram_message(bot_token: str, chat_id: str, text: str) -> tuple[bool, str]:
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            code = int(resp.getcode() or 0)
            return code == 200, f"http={code}"
    except urllib.error.HTTPError as exc:
        return False, f"http={int(getattr(exc, 'code', 0) or 0)}"
    except Exception as exc:
        return False, str(exc)


def _send_failure_alert_if_needed(
    *,
    state: dict[str, int | str],
    alert_enabled: bool,
    threshold: int,
    cooldown_seconds: int,
    bot_token: str,
    chat_ids: list[str],
    error_text: str,
    now: int,
) -> tuple[bool, str]:
    if not alert_enabled:
        return False, "disabled"
    if not _should_send_alert(
        consecutive_failures=int(state.get("consecutive_failures") or 0),
        threshold=threshold,
        last_alert_at=int(state.get("last_alert_at") or 0),
        cooldown_seconds=cooldown_seconds,
        now=now,
    ):
        return False, "not_due"
    if not bot_token or not chat_ids:
        return False, "missing_telegram_config"

    message = (
        "Hive google-token-refresher alert\n"
        f"consecutive_failures={int(state.get('consecutive_failures') or 0)}\n"
        f"threshold={threshold}\n"
        f"error={_truncate(error_text)}\n"
        f"time_unix={now}"
    )
    failed: list[str] = []
    for chat_id in chat_ids:
        sent, detail = _send_telegram_message(bot_token, chat_id, message)
        if not sent:
            failed.append(f"{chat_id}:{detail}")
    if failed:
        return False, "send_failed " + "; ".join(failed)
    state["last_alert_at"] = now
    state["last_alert_status"] = "sent"
    return True, "sent"


def main() -> int:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "").strip()
    token_file = Path(
        os.getenv("GOOGLE_ACCESS_TOKEN_FILE", "/data/storage/secrets/google_access_token").strip()
    )
    token_meta_file = Path(
        os.getenv("GOOGLE_ACCESS_TOKEN_META_FILE", f"{token_file}.meta.json").strip()
    )
    state_file = Path(os.getenv("GOOGLE_REFRESH_STATE_FILE", DEFAULT_STATE_PATH).strip())
    interval_s = int(os.getenv("GOOGLE_REFRESH_INTERVAL_SECONDS", "2700"))
    alert_enabled = _parse_bool("GOOGLE_REFRESH_ALERT_ENABLED", True)
    alert_threshold = _parse_positive_int(
        "GOOGLE_REFRESH_ALERT_FAILURE_THRESHOLD",
        DEFAULT_ALERT_THRESHOLD,
    )
    alert_cooldown_seconds = _parse_positive_int(
        "GOOGLE_REFRESH_ALERT_COOLDOWN_SECONDS",
        DEFAULT_ALERT_COOLDOWN_SECONDS,
    )
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids_raw = _resolve_alert_chat_ids_raw()
    chat_ids = _split_chat_ids(chat_ids_raw)
    state = _load_state(state_file)

    if not client_id or not client_secret or not refresh_token:
        print(
            "google-token-refresher: missing GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET/GOOGLE_REFRESH_TOKEN",
            flush=True,
        )
        return 2

    print(
        (
            "google-token-refresher: started; "
            f"interval={interval_s}s file={token_file} state={state_file} "
            f"alert_enabled={int(alert_enabled)} threshold={alert_threshold}"
        ),
        flush=True,
    )
    while True:
        now = int(time.time())
        try:
            token, expires_in = _refresh_token(client_id, client_secret, refresh_token)
            _atomic_write(token_file, token + "\n")
            expires_at = now + max(expires_in, 0) if expires_in > 0 else 0
            _atomic_write(
                token_meta_file,
                json.dumps(
                    {"expires_at": expires_at, "updated_at": now},
                    ensure_ascii=True,
                )
                + "\n",
            )
            state["consecutive_failures"] = 0
            state["total_success"] = int(state.get("total_success") or 0) + 1
            state["last_success_at"] = now
            state["last_expires_at"] = expires_at
            state["last_error"] = ""
            state["updated_at"] = now
            _save_state(state_file, state)
            print(f"google-token-refresher: refresh ok expires_in={expires_in}", flush=True)
        except Exception as exc:
            state["consecutive_failures"] = int(state.get("consecutive_failures") or 0) + 1
            state["total_failures"] = int(state.get("total_failures") or 0) + 1
            state["last_failure_at"] = now
            state["last_error"] = _truncate(str(exc), max_len=500)
            state["updated_at"] = now
            alert_sent, alert_detail = _send_failure_alert_if_needed(
                state=state,
                alert_enabled=alert_enabled,
                threshold=alert_threshold,
                cooldown_seconds=alert_cooldown_seconds,
                bot_token=bot_token,
                chat_ids=chat_ids,
                error_text=str(exc),
                now=now,
            )
            if alert_sent:
                print("google-token-refresher: failure alert sent to Telegram", flush=True)
            elif alert_detail not in {"disabled", "not_due"}:
                state["last_alert_status"] = alert_detail
                print(f"google-token-refresher: failure alert skipped ({alert_detail})", flush=True)
            _save_state(state_file, state)
            print(f"google-token-refresher: refresh failed: {exc}", flush=True)
        time.sleep(max(interval_s, 60))


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe Telegram updates and extract chat IDs for alert configuration."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import dotenv_values


def _load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values = dotenv_values(path)
    return {k: v for k, v in values.items() if isinstance(v, str)}


def _token(env_map: dict[str, str]) -> str:
    return (os.environ.get("TELEGRAM_BOT_TOKEN", "") or env_map.get("TELEGRAM_BOT_TOKEN", "")).strip()


def _extract_chat_ids(payload: dict) -> list[int]:
    out: list[int] = []
    for item in payload.get("result", []):
        source = (
            item.get("message")
            or item.get("edited_message")
            or (item.get("callback_query") or {}).get("message")
            or {}
        )
        chat = source.get("chat") if isinstance(source, dict) else None
        chat_id = chat.get("id") if isinstance(chat, dict) else None
        if chat_id is None:
            continue
        try:
            cid = int(chat_id)
        except Exception:
            continue
        if cid not in out:
            out.append(cid)
    return out


def _get_updates(token: str, *, timeout: int, limit: int) -> dict:
    params = urllib.parse.urlencode({"timeout": timeout, "limit": limit})
    url = f"https://api.telegram.org/bot{token}/getUpdates?{params}"
    with urllib.request.urlopen(url, timeout=max(timeout + 10, 20)) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _upsert_env(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out: list[str] = []
    found = False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Telegram chat id probe")
    parser.add_argument("--dotenv", default=".env", help="Env file path (default: .env)")
    parser.add_argument("--timeout", type=int, default=10, help="Long poll timeout seconds")
    parser.add_argument("--limit", type=int, default=20, help="Max updates per request")
    parser.add_argument(
        "--attempts",
        type=int,
        default=1,
        help="Number of getUpdates requests (default: 1)",
    )
    parser.add_argument(
        "--write-alert-env",
        action="store_true",
        help=(
            "Write discovered chat ids to GOOGLE_REFRESH_ALERT_CHAT_IDS and "
            "HIVE_TELEGRAM_TEST_CHAT_ID in .env"
        ),
    )
    args = parser.parse_args(argv)

    dotenv_path = Path(args.dotenv)
    env_map = _load_env(dotenv_path)
    token = _token(env_map)
    if not token:
        print("error: TELEGRAM_BOT_TOKEN is not configured")
        return 2

    discovered: list[int] = []
    for _ in range(max(1, args.attempts)):
        payload = _get_updates(token, timeout=max(0, args.timeout), limit=max(1, args.limit))
        ids = _extract_chat_ids(payload)
        for cid in ids:
            if cid not in discovered:
                discovered.append(cid)
        if discovered:
            break
        time.sleep(1)

    if discovered:
        value = ",".join(str(x) for x in discovered)
        print(f"chat_ids={value}")
        if args.write_alert_env:
            _upsert_env(dotenv_path, "GOOGLE_REFRESH_ALERT_CHAT_IDS", value)
            first_id = str(discovered[0])
            _upsert_env(dotenv_path, "HIVE_TELEGRAM_TEST_CHAT_ID", first_id)
            print(f"updated {dotenv_path}: GOOGLE_REFRESH_ALERT_CHAT_IDS={value}")
            print(f"updated {dotenv_path}: HIVE_TELEGRAM_TEST_CHAT_ID={first_id}")
        return 0

    print("chat_ids=none")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

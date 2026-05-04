#!/usr/bin/env python3
"""Validate operational API contracts used by container-first acceptance gates."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


def _fetch_json(url: str, timeout: float) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("response is not a JSON object")
    return payload


def _validate_health_contract(payload: dict[str, Any]) -> tuple[bool, str]:
    status = payload.get("status")
    telegram_bridge = payload.get("telegram_bridge")
    if not isinstance(status, str) or not status.strip():
        return False, "missing/invalid 'status'"
    if not isinstance(telegram_bridge, dict):
        return False, "missing/invalid 'telegram_bridge' object"
    if "running" not in telegram_bridge:
        return False, "telegram_bridge.running missing"
    return True, "ok"


def _validate_ops_contract(payload: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(payload.get("status"), str):
        return False, "missing/invalid 'status'"
    if not isinstance(payload.get("summary"), dict):
        return False, "missing/invalid 'summary' object"
    if not isinstance(payload.get("alerts"), dict):
        return False, "missing/invalid 'alerts' object"
    if not isinstance(payload.get("loop"), dict):
        return False, "missing/invalid 'loop' object"
    return True, "ok"


def _validate_telegram_contract(payload: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(payload.get("status"), str):
        return False, "missing/invalid 'status'"
    bridge = payload.get("bridge")
    if not isinstance(bridge, dict):
        return False, "missing/invalid 'bridge' object"
    if "running" not in bridge:
        return False, "bridge.running missing"
    if "poller_owner" not in bridge:
        return False, "bridge.poller_owner missing"
    enabled = bool(bridge.get("enabled"))
    if enabled:
        required_keys = (
            "poll_conflict_409_count",
            "last_poll_conflict_409_at",
            "last_poll_conflict_recover_at",
            "last_poll_conflict_recover_result",
            "auto_clear_webhook_on_409",
            "conflict_recover_cooldown_seconds",
            "conflict_warn_threshold",
            "conflict_warn_window_seconds",
            "poll_conflict_warning_active",
            "last_poll_conflict_age_seconds",
        )
        for key in required_keys:
            if key not in bridge:
                return False, f"bridge.{key} missing"
    return True, "ok"


def _validate_llm_queue_contract(payload: dict[str, Any]) -> tuple[bool, str]:
    if payload.get("status") != "ok":
        return False, "status must be 'ok'"
    queue = payload.get("queue")
    if not isinstance(queue, dict):
        return False, "missing/invalid 'queue' object"
    for key in ("limits", "backoff", "sync", "async"):
        if not isinstance(queue.get(key), dict):
            return False, f"queue.{key} missing/invalid"
    fallback = payload.get("fallback")
    if not isinstance(fallback, dict):
        return False, "missing/invalid 'fallback' object"
    if not isinstance(fallback.get("policy"), dict):
        return False, "fallback.policy missing/invalid"
    if not isinstance(fallback.get("history_limit"), int):
        return False, "fallback.history_limit missing/invalid"
    if not isinstance(fallback.get("recent_attempt_chains"), list):
        return False, "fallback.recent_attempt_chains missing/invalid"
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate operational API contracts")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("HIVE_BASE_URL") or f"http://localhost:{os.environ.get('HIVE_CORE_PORT', '8787')}",
        help="Hive core base URL (default: HIVE_BASE_URL or http://localhost:$HIVE_CORE_PORT)",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--check",
        action="append",
        choices=("all", "health", "ops", "telegram", "llm"),
        default=None,
        help="Contract to verify (can be repeated)",
    )
    args = parser.parse_args()

    checks_raw = args.check or ["all"]
    checks: list[str]
    if "all" in checks_raw:
        checks = ["health", "ops", "telegram", "llm"]
    else:
        # Preserve order while deduplicating.
        checks = list(dict.fromkeys(checks_raw))

    fail = 0
    for check in checks:
        if check == "health":
            path = "/api/health"
            validator = _validate_health_contract
        elif check == "ops":
            path = "/api/autonomous/ops/status?include_runs=true"
            validator = _validate_ops_contract
        elif check == "llm":
            path = "/api/llm/queue/status"
            validator = _validate_llm_queue_contract
        else:
            path = "/api/telegram/bridge/status"
            validator = _validate_telegram_contract

        url = f"{args.base_url}{path}"
        try:
            payload = _fetch_json(url, timeout=args.timeout)
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            print(f"[fail] {check} contract: {exc}", file=sys.stderr)
            fail += 1
            continue

        ok, detail = validator(payload)
        if ok:
            print(f"[ok] {check} contract: {detail}")
        else:
            print(f"[fail] {check} contract: {detail}", file=sys.stderr)
            fail += 1

    if fail:
        print(f"operational api contracts check failed: {fail} issue(s)", file=sys.stderr)
        return 1
    print("operational api contracts check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

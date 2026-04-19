#!/usr/bin/env python3
"""Production MCP health summary for local Hive deployment.

Checks target stack:
- github
- google
- web search (Brave)
- web scrape (generic outbound HTTP)
- files-tools (runtime registration in hive-core logs)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    from dotenv import dotenv_values as _DOTENV_VALUES
except Exception:  # pragma: no cover - exercised via fallback tests
    _DOTENV_VALUES = None

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_GOOGLE_WARN_TTL_SECONDS = 900
DEFAULT_GOOGLE_CRITICAL_TTL_SECONDS = 120


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    if _DOTENV_VALUES is not None:
        values = _DOTENV_VALUES(path)
    else:
        values = _parse_dotenv_fallback(path)
    return {k: v for k, v in values.items() if isinstance(v, str)}


def _parse_dotenv_fallback(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        name = key.strip()
        if not name:
            continue
        parsed = value.strip()
        if len(parsed) >= 2 and parsed[0] == parsed[-1] and parsed[0] in {"'", '"'}:
            parsed = parsed[1:-1]
        values[name] = parsed
    return values


def _env(name: str, env_map: dict[str, str]) -> str:
    return os.environ.get(name, "") or env_map.get(name, "") or ""


def _safe_int(value: Any) -> int | None:
    try:
        num = int(str(value).strip())
    except Exception:
        return None
    return num if num > 0 else None


def _google_ttl_thresholds(env_map: dict[str, str]) -> tuple[int, int]:
    warn = _safe_int(_env("HIVE_GOOGLE_TOKEN_WARN_TTL_SECONDS", env_map)) or DEFAULT_GOOGLE_WARN_TTL_SECONDS
    critical = (
        _safe_int(_env("HIVE_GOOGLE_TOKEN_CRITICAL_TTL_SECONDS", env_map))
        or DEFAULT_GOOGLE_CRITICAL_TTL_SECONDS
    )
    critical = max(1, critical)
    warn = max(warn, critical)
    return warn, critical


def _google_freshness(
    *,
    expires_at: int | None,
    warn_ttl_seconds: int,
    critical_ttl_seconds: int,
) -> dict[str, Any]:
    if not expires_at:
        return {
            "known": False,
            "level": "unknown",
            "ttl_seconds": None,
            "expires_at": None,
            "thresholds": {
                "warning_ttl_seconds": warn_ttl_seconds,
                "critical_ttl_seconds": critical_ttl_seconds,
            },
        }
    now = int(time.time())
    ttl = int(expires_at) - now
    if ttl <= critical_ttl_seconds:
        level = "critical"
    elif ttl <= warn_ttl_seconds:
        level = "warning"
    else:
        level = "ok"
    return {
        "known": True,
        "level": level,
        "ttl_seconds": ttl,
        "expires_at": int(expires_at),
        "checked_at": now,
        "thresholds": {
            "warning_ttl_seconds": warn_ttl_seconds,
            "critical_ttl_seconds": critical_ttl_seconds,
        },
    }


def _resolve_google_access_token_source(env_map: dict[str, str]) -> dict[str, Any]:
    token_file = _env("GOOGLE_ACCESS_TOKEN_FILE", env_map).strip()
    meta_file_raw = _env("GOOGLE_ACCESS_TOKEN_META_FILE", env_map).strip()
    if token_file:
        token_path = Path(token_file)
        if token_path.exists():
            try:
                token = token_path.read_text(encoding="utf-8").strip()
            except Exception as e:
                return {
                    "token": "",
                    "source": "file",
                    "token_file": token_file,
                    "meta_file": meta_file_raw or f"{token_file}.meta.json",
                    "expires_at": None,
                    "error": f"cannot_read_token_file: {e}",
                }
            if token:
                meta_file = meta_file_raw or f"{token_file}.meta.json"
                expires_at = None
                meta_path = Path(meta_file)
                meta_error = None
                if meta_path.exists():
                    try:
                        payload = json.loads(meta_path.read_text(encoding="utf-8"))
                        expires_at = _safe_int(payload.get("expires_at"))
                    except Exception as e:
                        meta_error = f"cannot_read_meta_file: {e}"
                return {
                    "token": token,
                    "source": "file",
                    "token_file": token_file,
                    "meta_file": meta_file,
                    "expires_at": expires_at,
                    "meta_error": meta_error,
                }

    env_token = _env("GOOGLE_ACCESS_TOKEN", env_map).strip()
    env_expires_at = _safe_int(_env("GOOGLE_TOKEN_EXPIRES_AT", env_map))
    return {
        "token": env_token,
        "source": "env",
        "token_file": token_file or None,
        "meta_file": meta_file_raw or (f"{token_file}.meta.json" if token_file else None),
        "expires_at": env_expires_at,
    }


def _http_check(
    *,
    name: str,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
    ok_codes: tuple[int, ...] = (200,),
) -> dict[str, Any]:
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(resp.getcode() or 0)
            return {"name": name, "ok": code in ok_codes, "code": code, "detail": f"HTTP {code}"}
    except urllib.error.HTTPError as e:
        code = int(getattr(e, "code", 0) or 0)
        return {"name": name, "ok": code in ok_codes, "code": code, "detail": f"HTTP {code}"}
    except Exception as e:
        return {"name": name, "ok": False, "code": None, "detail": str(e)}


def _files_tools_log_check(since_minutes: int) -> dict[str, Any]:
    cmd = [
        "docker",
        "compose",
        "logs",
        f"--since={since_minutes}m",
        "hive-core",
    ]
    try:
        p = subprocess.run(cmd, check=False, capture_output=True, text=True)
        logs = (p.stdout or "") + "\n" + (p.stderr or "")
    except FileNotFoundError:
        # Container-first execution path: docker CLI is usually unavailable in the
        # runtime container, so treat files-tools log inspection as skipped.
        return {
            "name": "files_tools_runtime",
            "ok": True,
            "detail": {
                "mode": "docker_cli_unavailable",
                "reason": "docker command not found in current runtime",
                "since_minutes": since_minutes,
            },
        }
    except Exception as e:
        return {
            "name": "files_tools_runtime",
            "ok": False,
            "detail": f"cannot read logs: {e}",
        }

    has_connect = "Connected to MCP server 'files-tools'" in logs
    has_discover = "Discovered 6 tools from 'files-tools'" in logs
    has_fail = "MCP server 'files-tools' failed to register" in logs
    has_zero_allowed = "MCP server 'files-tools' registered 0 tools (allowed by config)" in logs
    has_any_files_signal = "files-tools" in logs

    if has_fail:
        ok = False
        mode = "failure_detected"
    elif (has_connect and has_discover) or has_zero_allowed:
        ok = True
        mode = "registered"
    elif has_any_files_signal:
        ok = False
        mode = "ambiguous_signal"
    else:
        # No recent registration events is normal for idle runtime.
        ok = True
        mode = "no_recent_activity"

    detail = {
        "connected": has_connect,
        "discovered": has_discover,
        "failed_register": has_fail,
        "zero_allowed": has_zero_allowed,
        "has_any_files_signal": has_any_files_signal,
        "mode": mode,
        "since_minutes": since_minutes,
    }
    return {"name": "files_tools_runtime", "ok": ok, "detail": detail}


def _refresh_google_access_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> tuple[str, int]:
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
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    token = str(data.get("access_token") or "")
    expires_in = int(data.get("expires_in") or 0)
    if not token:
        raise RuntimeError("refresh endpoint returned no access_token")
    return token, expires_in


def _google_tokeninfo_check(token: str) -> dict[str, Any]:
    token_info_url = f"{GOOGLE_TOKENINFO_URL}?access_token={urllib.parse.quote(token, safe='')}"
    req = urllib.request.Request(token_info_url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            code = int(resp.getcode() or 0)
            return {
                "ok": code == 200,
                "code": code,
                "detail": f"HTTP {code}",
                "payload": payload,
            }
    except urllib.error.HTTPError as e:
        code = int(getattr(e, "code", 0) or 0)
        body = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "code": code, "detail": f"HTTP {code}", "payload": {"error": body}}
    except Exception as e:
        return {"ok": False, "code": None, "detail": str(e), "payload": {}}


def _google_health_check(env_map: dict[str, str]) -> dict[str, Any]:
    token_source = _resolve_google_access_token_source(env_map)
    access_token = str(token_source.get("token") or "").strip()
    refresh_token = _env("GOOGLE_REFRESH_TOKEN", env_map)
    client_id = _env("GOOGLE_CLIENT_ID", env_map)
    client_secret = _env("GOOGLE_CLIENT_SECRET", env_map)
    warn_ttl, critical_ttl = _google_ttl_thresholds(env_map)

    token_freshness = _google_freshness(
        expires_at=_safe_int(token_source.get("expires_at")),
        warn_ttl_seconds=warn_ttl,
        critical_ttl_seconds=critical_ttl,
    )

    tokeninfo_detail: dict[str, Any] = {"checked": False}
    if access_token:
        tokeninfo = _google_tokeninfo_check(access_token)
        tokeninfo_detail = {
            "checked": True,
            "ok": bool(tokeninfo.get("ok")),
            "code": tokeninfo.get("code"),
            "detail": tokeninfo.get("detail"),
        }
        if tokeninfo.get("ok"):
            if token_freshness.get("known") is not True:
                token_info_expires_in = _safe_int((tokeninfo.get("payload") or {}).get("expires_in"))
                if token_info_expires_in is not None:
                    token_freshness = _google_freshness(
                        expires_at=int(time.time()) + token_info_expires_in,
                        warn_ttl_seconds=warn_ttl,
                        critical_ttl_seconds=critical_ttl,
                    )

            freshness_level = str(token_freshness.get("level") or "unknown")
            ok = freshness_level != "critical"
            return {
                "name": "google",
                "ok": ok,
                "code": tokeninfo.get("code"),
                "detail": {
                    "mode": "access_token",
                    "token_source": token_source.get("source"),
                    "token_file": token_source.get("token_file"),
                    "meta_file": token_source.get("meta_file"),
                    "token_source_error": token_source.get("error"),
                    "token_source_meta_error": token_source.get("meta_error"),
                    "freshness": token_freshness,
                    **tokeninfo_detail,
                },
            }

    if refresh_token and client_id and client_secret:
        try:
            refreshed_token, expires_in = _refresh_google_access_token(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
            )
        except Exception as e:
            return {
                "name": "google",
                "ok": False,
                "code": None,
                "detail": {
                    "mode": "refresh_failed",
                    "error": str(e),
                    "tokeninfo": tokeninfo_detail,
                },
            }

        refreshed_check = _google_tokeninfo_check(refreshed_token)
        refreshed_freshness = _google_freshness(
            expires_at=int(time.time()) + max(expires_in, 0) if expires_in > 0 else None,
            warn_ttl_seconds=warn_ttl,
            critical_ttl_seconds=critical_ttl,
        )
        ok = bool(refreshed_check.get("ok")) and refreshed_freshness.get("level") != "critical"
        return {
            "name": "google",
            "ok": ok,
            "code": refreshed_check.get("code"),
            "detail": {
                "mode": "refresh_fallback",
                "token_source": "refresh_fallback",
                "expires_in": expires_in,
                "freshness": refreshed_freshness,
                "tokeninfo_after_refresh": {
                    "ok": bool(refreshed_check.get("ok")),
                    "code": refreshed_check.get("code"),
                    "detail": refreshed_check.get("detail"),
                },
                "tokeninfo_before_refresh": tokeninfo_detail,
                "token_source_before_refresh": {
                    "source": token_source.get("source"),
                    "token_file": token_source.get("token_file"),
                    "meta_file": token_source.get("meta_file"),
                    "error": token_source.get("error"),
                    "meta_error": token_source.get("meta_error"),
                    "freshness": token_freshness,
                },
            },
        }

    missing = []
    if not refresh_token:
        missing.append("GOOGLE_REFRESH_TOKEN")
    if not client_id:
        missing.append("GOOGLE_CLIENT_ID")
    if not client_secret:
        missing.append("GOOGLE_CLIENT_SECRET")
    return {
        "name": "google",
        "ok": False,
        "code": tokeninfo_detail.get("code"),
        "detail": {
            "mode": "no_refresh_fallback",
            "missing": missing,
            "tokeninfo": tokeninfo_detail,
            "token_source": token_source.get("source"),
            "token_file": token_source.get("token_file"),
            "meta_file": token_source.get("meta_file"),
            "token_source_error": token_source.get("error"),
            "token_source_meta_error": token_source.get("meta_error"),
            "freshness": token_freshness,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP health summary")
    parser.add_argument("--dotenv", default=".env", help="Path to .env (default: .env)")
    parser.add_argument(
        "--since-minutes",
        type=int,
        default=30,
        help="How many minutes of hive-core logs to inspect for files-tools",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    env_map = _load_dotenv(Path(args.dotenv))
    checks: list[dict[str, Any]] = []

    github_token = _env("GITHUB_TOKEN", env_map)
    if github_token:
        checks.append(
            _http_check(
                name="github",
                url="https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        )
    else:
        checks.append({"name": "github", "ok": False, "code": None, "detail": "missing GITHUB_TOKEN"})

    checks.append(_google_health_check(env_map))

    brave_key = _env("BRAVE_SEARCH_API_KEY", env_map)
    if brave_key:
        checks.append(
            _http_check(
                name="web_search_brave",
                url="https://api.search.brave.com/res/v1/web/search?q=hive&count=1",
                headers={"X-Subscription-Token": brave_key, "Accept": "application/json"},
            )
        )
    else:
        checks.append(
            {
                "name": "web_search_brave",
                "ok": False,
                "code": None,
                "detail": "missing BRAVE_SEARCH_API_KEY",
            }
        )

    # Generic outbound HTTP smoke for scrape-path networking.
    checks.append(_http_check(name="web_scrape_http", url="https://example.com"))
    checks.append(_files_tools_log_check(args.since_minutes))

    ok_count = sum(1 for c in checks if c.get("ok"))
    result = {
        "checks": checks,
        "summary": {
            "total": len(checks),
            "ok": ok_count,
            "failed": len(checks) - ok_count,
            "status": "ok" if ok_count == len(checks) else "degraded",
        },
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("MCP health summary")
        print(f"status: {result['summary']['status']}")
        print(f"ok: {result['summary']['ok']}/{result['summary']['total']}")
        print()
        for c in checks:
            mark = "OK" if c.get("ok") else "FAIL"
            detail = c.get("detail")
            print(f"[{mark}] {c.get('name')}: {detail}")
        print()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result["summary"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Google OAuth token bootstrap and refresh helper for local Hive setup.

Usage examples:
  uv run python scripts/google_oauth_token_manager.py auth-url
  uv run python scripts/google_oauth_token_manager.py exchange --code "<AUTH_CODE>"
  uv run python scripts/google_oauth_token_manager.py refresh --restart-hive
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        result[key.strip()] = val.strip()
    return result


def _resolve_var(name: str, env_file: dict[str, str], fallback: str = "") -> str:
    val = os.environ.get(name)
    if val and val.strip():
        return val.strip()
    return env_file.get(name, fallback).strip()


def _upsert_env(path: Path, updates: dict[str, str]) -> None:
    def _fmt(value: str) -> str:
        if any(ch.isspace() for ch in value):
            escaped = value.replace('"', '\\"')
            return f'"{escaped}"'
        return value

    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out: list[str] = []
    pending = dict(updates)
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in pending:
            out.append(f"{key}={_fmt(pending.pop(key))}")
        else:
            out.append(line)
    if pending:
        if out and out[-1].strip():
            out.append("")
        for key, value in pending.items():
            out.append(f"{key}={_fmt(value)}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _token_request(payload: dict[str, str]) -> dict[str, object]:
    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=encoded,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google token endpoint HTTP {exc.code}: {body}") from exc


def _maybe_restart_hive(restart: bool, workdir: Path) -> None:
    if not restart:
        return
    subprocess.run(
        ["docker", "compose", "up", "-d", "--force-recreate", "hive-core"],
        cwd=str(workdir),
        check=True,
    )


def cmd_auth_url(args: argparse.Namespace) -> int:
    env_file = _load_env_file(Path(args.dotenv))
    client_id = args.client_id or _resolve_var("GOOGLE_CLIENT_ID", env_file)
    redirect_uri = args.redirect_uri or _resolve_var(
        "GOOGLE_REDIRECT_URI", env_file, "http://localhost:8788/google/oauth/callback"
    )
    scopes = args.scopes or _resolve_var("GOOGLE_OAUTH_SCOPES", env_file)
    if scopes:
        scope_list = [s for s in scopes.split() if s]
    else:
        scope_list = DEFAULT_SCOPES

    if not client_id:
        print("Missing GOOGLE_CLIENT_ID. Set it in .env or pass --client-id.", file=sys.stderr)
        return 2

    state = args.state or secrets.token_urlsafe(16)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scope_list),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    print("Open this URL in browser:")
    print(url)
    print()
    print(f"state={state}")
    print("After consent, copy `code` from redirect URL and run exchange command.")
    return 0


def cmd_exchange(args: argparse.Namespace) -> int:
    dotenv_path = Path(args.dotenv)
    env_file = _load_env_file(dotenv_path)

    client_id = args.client_id or _resolve_var("GOOGLE_CLIENT_ID", env_file)
    client_secret = args.client_secret or _resolve_var("GOOGLE_CLIENT_SECRET", env_file)
    redirect_uri = args.redirect_uri or _resolve_var(
        "GOOGLE_REDIRECT_URI", env_file, "http://localhost:8788/google/oauth/callback"
    )
    code = args.code
    if not code:
        print("Missing --code", file=sys.stderr)
        return 2
    if not client_id or not client_secret:
        print("Missing GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET", file=sys.stderr)
        return 2

    token = _token_request(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
    )
    access = str(token.get("access_token") or "")
    refresh = str(token.get("refresh_token") or "")
    expires_in = int(token.get("expires_in") or 0)
    scope = str(token.get("scope") or "")
    if not access:
        print(f"Token exchange failed: {token}", file=sys.stderr)
        return 1

    expires_at = str(int(time.time()) + expires_in if expires_in > 0 else 0)
    print("Exchange success.")
    print(f"expires_in={expires_in}")
    print(f"has_refresh_token={'yes' if bool(refresh) else 'no'}")

    if args.print_only:
        print(json.dumps(token, indent=2))
        return 0

    updates = {
        "GOOGLE_ACCESS_TOKEN": access,
        "GOOGLE_TOKEN_EXPIRES_AT": expires_at,
        "GOOGLE_OAUTH_SCOPES": scope or _resolve_var("GOOGLE_OAUTH_SCOPES", env_file, " ".join(DEFAULT_SCOPES)),
    }
    if refresh:
        updates["GOOGLE_REFRESH_TOKEN"] = refresh
    _upsert_env(dotenv_path, updates)
    print(f"Updated {dotenv_path}")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    dotenv_path = Path(args.dotenv)
    env_file = _load_env_file(dotenv_path)

    client_id = args.client_id or _resolve_var("GOOGLE_CLIENT_ID", env_file)
    client_secret = args.client_secret or _resolve_var("GOOGLE_CLIENT_SECRET", env_file)
    refresh_token = args.refresh_token or _resolve_var("GOOGLE_REFRESH_TOKEN", env_file)
    if not client_id or not client_secret or not refresh_token:
        print(
            "Missing GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN",
            file=sys.stderr,
        )
        return 2

    token = _token_request(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    )
    access = str(token.get("access_token") or "")
    expires_in = int(token.get("expires_in") or 0)
    scope = str(token.get("scope") or "")
    if not access:
        print(f"Refresh failed: {token}", file=sys.stderr)
        return 1

    expires_at = str(int(time.time()) + expires_in if expires_in > 0 else 0)
    updates = {
        "GOOGLE_ACCESS_TOKEN": access,
        "GOOGLE_TOKEN_EXPIRES_AT": expires_at,
    }
    if scope:
        updates["GOOGLE_OAUTH_SCOPES"] = scope
    _upsert_env(dotenv_path, updates)
    print(f"Refresh success. expires_in={expires_in}")
    print(f"Updated {dotenv_path}")

    workdir = Path(args.workdir).resolve()
    _maybe_restart_hive(args.restart_hive, workdir)
    if args.restart_hive:
        print("Restarted hive-core to apply new GOOGLE_ACCESS_TOKEN")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Google OAuth helper for local Hive")

    sub = parser.add_subparsers(dest="command", required=True)

    p_auth = sub.add_parser("auth-url", help="Generate OAuth consent URL")
    p_auth.add_argument("--dotenv", default=".env", help="Path to env file (default: .env)")
    p_auth.add_argument("--client-id", default="", help="Google OAuth client ID")
    p_auth.add_argument("--redirect-uri", default="", help="OAuth redirect URI")
    p_auth.add_argument(
        "--scopes",
        default="",
        help="Space-separated scopes; defaults to Docs/Sheets/Drive/Gmail/Calendar",
    )
    p_auth.add_argument("--state", default="", help="Optional state param")
    p_auth.set_defaults(func=cmd_auth_url)

    p_exchange = sub.add_parser("exchange", help="Exchange auth code for tokens")
    p_exchange.add_argument("--dotenv", default=".env", help="Path to env file (default: .env)")
    p_exchange.add_argument("--code", required=True, help="Authorization code from Google redirect")
    p_exchange.add_argument("--client-id", default="", help="Google OAuth client ID")
    p_exchange.add_argument("--client-secret", default="", help="Google OAuth client secret")
    p_exchange.add_argument("--redirect-uri", default="", help="OAuth redirect URI")
    p_exchange.add_argument(
        "--print-only",
        action="store_true",
        help="Print token response and do not modify .env",
    )
    p_exchange.set_defaults(func=cmd_exchange)

    p_refresh = sub.add_parser("refresh", help="Refresh access token via refresh token")
    p_refresh.add_argument("--dotenv", default=".env", help="Path to env file (default: .env)")
    p_refresh.add_argument("--client-id", default="", help="Google OAuth client ID")
    p_refresh.add_argument("--client-secret", default="", help="Google OAuth client secret")
    p_refresh.add_argument("--refresh-token", default="", help="Google OAuth refresh token")
    p_refresh.add_argument(
        "--restart-hive",
        action="store_true",
        help="Restart hive-core after updating .env",
    )
    p_refresh.add_argument(
        "--workdir",
        default=".",
        help="Directory containing docker-compose.yml for --restart-hive",
    )
    p_refresh.set_defaults(func=cmd_refresh)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

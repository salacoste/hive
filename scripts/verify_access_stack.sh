#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${1:-.env}"

ok() { printf '[OK] %s\n' "$1"; }
warn() { printf '[WARN] %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1"; exit 1; }

docker_mode_available() {
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1
}

run_socket_probe() {
  local env_name="$1"
  local fallback_url="$2"
  local log_file="$3"
  local mode="$4"
  local probe_cmd="UV_ENV_NAME='${env_name}' UV_FALLBACK_URL='${fallback_url}' uv run python - <<'PY'
import os
import socket
import urllib.parse as u

env_name = os.environ['UV_ENV_NAME']
fallback_url = os.environ['UV_FALLBACK_URL']
parsed = u.urlparse(os.environ.get(env_name, fallback_url))
host = parsed.hostname
port = parsed.port

if not host or not port:
    raise SystemExit(f'invalid endpoint for {env_name}: {parsed.geturl()}')

sock = socket.create_connection((host, port), timeout=5)
sock.close()
print('ok')
PY"

  if [[ "$mode" == "docker" ]]; then
    docker compose exec -T hive-core sh -lc "$probe_cmd" >"$log_file" 2>&1
  else
    sh -lc "$probe_cmd" >"$log_file" 2>&1
  fi
}

run_google_refresh_state_probe() {
  local mode="$1"
  local probe_cmd="uv run python - <<'PY'
import json
import os
from pathlib import Path

state_path = Path(os.getenv('GOOGLE_REFRESH_STATE_FILE', '/data/storage/secrets/google_refresh_state.json'))
threshold = int(os.getenv('GOOGLE_REFRESH_ALERT_FAILURE_THRESHOLD', '3') or '3')
if not state_path.exists():
    print('WARN state_missing')
    raise SystemExit(1)

try:
    state = json.loads(state_path.read_text(encoding='utf-8'))
except Exception as exc:
    print(f'WARN state_unreadable {exc}')
    raise SystemExit(1)

consecutive = int(state.get('consecutive_failures') or 0)
total_failures = int(state.get('total_failures') or 0)
last_success_at = int(state.get('last_success_at') or 0)
if consecutive >= threshold:
    print(
        f'WARN consecutive_failures={consecutive} threshold={threshold} '
        f'total_failures={total_failures} last_success_at={last_success_at}'
    )
    raise SystemExit(1)
print(
    f'OK consecutive_failures={consecutive} threshold={threshold} '
    f'total_failures={total_failures} last_success_at={last_success_at}'
)
PY"

  if [[ "$mode" == "docker" ]]; then
    docker compose exec -T hive-core sh -lc "$probe_cmd" 2>/tmp/hive-google-refresh-state.log || true
  else
    sh -lc "$probe_cmd" 2>/tmp/hive-google-refresh-state.log || true
  fi
}

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  warn "env file not found: ${ENV_FILE} (using current shell env only)"
fi

echo "Verifying access stack (GitHub / DB / Google / Telegram)"
echo

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  code="$(curl -sS -o /tmp/hive-gh-user.json -w '%{http_code}' \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/user || true)"
  if [[ "$code" == "200" ]]; then
    login="$(grep -o '"login":"[^"]*"' /tmp/hive-gh-user.json | head -n1 | cut -d'"' -f4 || true)"
    ok "GitHub token valid${login:+ (user=${login})}"
  else
    warn "GitHub token check failed (http=${code})"
  fi
else
  warn "GITHUB_TOKEN is not set"
fi

if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  code="$(curl -sS -o /tmp/hive-tg-me.json -w '%{http_code}' \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" || true)"
  if [[ "$code" == "200" ]]; then
    ok "Telegram bot token accepted"
  else
    warn "Telegram token check failed (http=${code})"
  fi
else
  warn "TELEGRAM_BOT_TOKEN is not set"
fi

google_status="$(uv run python - <<'PY'
import json
import os
import urllib.parse
import urllib.request

TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def tokeninfo(token: str) -> tuple[bool, int, dict]:
    url = TOKENINFO_URL + "?access_token=" + urllib.parse.quote(token, safe="")
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, int(resp.getcode() or 0), data
    except Exception as exc:
        code = int(getattr(exc, "code", 0) or 0)
        return False, code, {}


def refresh() -> tuple[bool, str, int]:
    cid = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    csec = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    rtok = os.getenv("GOOGLE_REFRESH_TOKEN", "").strip()
    if not cid or not csec or not rtok:
        return False, "", 0
    payload = urllib.parse.urlencode(
        {
            "client_id": cid,
            "client_secret": csec,
            "refresh_token": rtok,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return False, "", 0
    tok = str(data.get("access_token") or "")
    exp = int(data.get("expires_in") or 0)
    return bool(tok), tok, exp


access = os.getenv("GOOGLE_ACCESS_TOKEN", "").strip()
if access:
    ok, _, info = tokeninfo(access)
    if ok:
        scope = str(info.get("scope") or "").strip()
        print("OK access-token " + (scope if scope else "-"))
        raise SystemExit(0)

ref_ok, new_token, exp = refresh()
if ref_ok:
    ok, _, info = tokeninfo(new_token)
    if ok:
        scope = str(info.get("scope") or "").strip()
        print(f"OK refresh-fallback expires_in={exp} " + (scope if scope else "-"))
        raise SystemExit(0)
    print("WARN refresh-token works but tokeninfo still failed")
    raise SystemExit(1)

if access:
    print("WARN access token invalid and refresh fallback unavailable")
else:
    print("WARN access token missing and refresh fallback unavailable")
raise SystemExit(1)
PY
)"
if [[ "$google_status" == OK* ]]; then
  ok "Google token path accepted (${google_status#OK })"
else
  warn "Google token check failed (${google_status})"
fi

if [[ -n "${GOOGLE_REFRESH_TOKEN:-}" && -n "${GOOGLE_CLIENT_ID:-}" && -n "${GOOGLE_CLIENT_SECRET:-}" ]]; then
  ok "Google refresh flow configured (GOOGLE_REFRESH_TOKEN + client id/secret present)"
else
  warn "Google refresh flow is not fully configured (need GOOGLE_REFRESH_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)"
fi

runtime_mode="container"
if docker_mode_available; then
  runtime_mode="docker"
fi

if run_socket_probe "REDIS_URL" "redis://redis:6379/0" "/tmp/hive-redis-check.log" "$runtime_mode"; then
  ok "Redis reachable from hive-core"
else
  warn "Redis check failed (see /tmp/hive-redis-check.log)"
fi

if run_socket_probe "DATABASE_URL" "postgresql://hive:hive@postgres:5432/hive" "/tmp/hive-postgres-check.log" "$runtime_mode"; then
  ok "Postgres reachable from hive-core"
else
  warn "Postgres check failed (see /tmp/hive-postgres-check.log)"
fi

if [[ "$runtime_mode" == "docker" ]]; then
  if docker inspect -f '{{.State.Status}}' hive-google-token-refresher >/tmp/hive-google-refresher-status.log 2>&1; then
    status="$(cat /tmp/hive-google-refresher-status.log)"
    if [[ "$status" == "running" ]]; then
      ok "google-token-refresher container is running"
    else
      warn "google-token-refresher status=${status}"
    fi
  else
    warn "google-token-refresher container not found"
  fi
else
  ok "google-token-refresher container check skipped (docker CLI unavailable in container runtime)"
fi

google_refresh_state="$(run_google_refresh_state_probe "$runtime_mode")"
if [[ "$google_refresh_state" == OK* ]]; then
  ok "Google refresher state healthy (${google_refresh_state#OK })"
else
  warn "Google refresher state degraded (${google_refresh_state:-unknown}; see /tmp/hive-google-refresh-state.log)"
fi

echo
echo "Access stack verification complete."

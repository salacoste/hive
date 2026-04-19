#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${HIVE_CORE_PORT:-8787}"
HEALTH_URL="http://localhost:${PORT}/api/health"

ok() { printf '[OK] %s\n' "$1"; }
warn() { printf '[WARN] %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1"; exit 1; }

echo "Hive local production checklist"
echo "Root: ${ROOT_DIR}"
echo

if ! command -v docker >/dev/null 2>&1; then
  fail "docker not found"
fi
if ! docker compose version >/dev/null 2>&1; then
  fail "docker compose is not available"
fi
ok "docker + docker compose available"

if ! docker compose ps >/dev/null 2>&1; then
  fail "docker compose project is not readable"
fi
ok "docker compose project readable"

hive_status="$(docker inspect -f '{{.State.Health.Status}}' hive-core 2>/dev/null || true)"
redis_status="$(docker inspect -f '{{.State.Health.Status}}' hive-redis 2>/dev/null || true)"
postgres_status="$(docker inspect -f '{{.State.Health.Status}}' hive-postgres 2>/dev/null || true)"

[[ "$hive_status" == "healthy" ]] || fail "hive-core is not healthy (status=${hive_status:-missing})"
[[ "$redis_status" == "healthy" ]] || fail "hive-redis is not healthy (status=${redis_status:-missing})"
[[ "$postgres_status" == "healthy" ]] || fail "hive-postgres is not healthy (status=${postgres_status:-missing})"
ok "containers healthy (hive-core, redis, postgres)"

google_refresher_status="$(docker inspect -f '{{.State.Status}}' hive-google-token-refresher 2>/dev/null || true)"
if [[ "$google_refresher_status" == "running" ]]; then
  ok "google-token-refresher container running"
else
  warn "google-token-refresher not running (status=${google_refresher_status:-missing})"
fi

if curl -fsS "$HEALTH_URL" >/dev/null; then
  ok "api health endpoint responds (${HEALTH_URL})"
else
  fail "api health endpoint failed (${HEALTH_URL})"
fi

if ./scripts/check_runtime_parity.sh >/tmp/hive-runtime-parity.log 2>&1; then
  tail -n +1 /tmp/hive-runtime-parity.log
  ok "runtime parity check passed"
else
  tail -n +1 /tmp/hive-runtime-parity.log || true
  fail "runtime parity check failed"
fi

if docker compose exec -T hive-core sh -lc 'getent hosts redis postgres >/dev/null'; then
  ok "internal DNS resolves redis + postgres"
else
  fail "hive-core cannot resolve redis/postgres hostnames"
fi

if uv run python scripts/audit_mcp_credentials.py --bundle local_pro_stack >/tmp/hive-audit.log; then
  tail -n +1 /tmp/hive-audit.log
  if grep -q "^Missing: 0$" /tmp/hive-audit.log; then
    ok "local_pro_stack credentials complete"
  else
    warn "local_pro_stack credentials have gaps (see output above)"
  fi
else
  warn "credential audit command failed"
fi

echo
echo "Checklist complete."

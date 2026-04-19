#!/usr/bin/env bash
set -euo pipefail

# One-shot local production setup:
# - audit target MCP stack credentials
# - build and start docker compose services
# - wait until services are healthy
# - open Hive dashboard in browser

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/4] Auditing target MCP stack credentials..."
uv run python scripts/audit_mcp_credentials.py --bundle local_pro_stack || true

echo "[2/4] Building and starting local stack..."
docker compose up -d --build

echo "[3/4] Waiting for services to become healthy..."
deadline=$((SECONDS + 240))
while :; do
  hive_ok=false
  redis_ok=false
  postgres_ok=false

  if [[ "$(docker inspect -f '{{.State.Health.Status}}' hive-core 2>/dev/null || true)" == "healthy" ]]; then
    hive_ok=true
  fi
  if [[ "$(docker inspect -f '{{.State.Health.Status}}' hive-redis 2>/dev/null || true)" == "healthy" ]]; then
    redis_ok=true
  fi
  if [[ "$(docker inspect -f '{{.State.Health.Status}}' hive-postgres 2>/dev/null || true)" == "healthy" ]]; then
    postgres_ok=true
  fi

  if $hive_ok && $redis_ok && $postgres_ok; then
    break
  fi

  if (( SECONDS >= deadline )); then
    echo "Timed out waiting for healthy services."
    docker compose ps
    exit 1
  fi

  sleep 3
done

PORT="${HIVE_CORE_PORT:-8787}"
URL="http://localhost:${PORT}"

echo "[4/4] Verifying Hive API health..."
curl -fsS "${URL}/api/health" >/dev/null
echo "Hive is ready: ${URL}"
echo "API health: ${URL}/api/health"

if command -v open >/dev/null 2>&1; then
  open "$URL" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
fi

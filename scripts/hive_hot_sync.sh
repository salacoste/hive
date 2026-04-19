#!/usr/bin/env bash
set -euo pipefail

# Fast local code/config sync into running hive-core container, without full image rebuild.
# Usage:
#   ./scripts/hive_hot_sync.sh                         # sync default critical files
#   ./scripts/hive_hot_sync.sh path1 path2 ...         # sync custom file list

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DEFAULT_FILES=(
  "tools/mcp_server.py"
  "tools/coder_tools_server.py"
  "tools/files_server.py"
  "tools/mcp_servers.json"
  "core/framework/agents/queen/mcp_servers.json"
)

if [[ $# -gt 0 ]]; then
  FILES=("$@")
else
  FILES=("${DEFAULT_FILES[@]}")
fi

for f in "${FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "skip missing: $f"
    continue
  fi
  echo "sync: $f"
  docker cp "$f" hive-core:"/app/$f"
done

echo "restart hive-core"
docker compose restart hive-core >/dev/null

for i in {1..30}; do
  s=$(docker inspect -f '{{.State.Health.Status}}' hive-core 2>/dev/null || echo starting)
  echo "[$i] hive-core health=$s"
  if [[ "$s" == "healthy" ]]; then
    break
  fi
  sleep 2
done

curl -fsS "http://localhost:${HIVE_CORE_PORT:-8787}/api/health"
echo

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -eq 0 ]]; then
  cat <<'EOF'
Usage:
  ./scripts/hive_ops_run.sh [--build] <command...>

Examples:
  ./scripts/hive_ops_run.sh uv run --no-project python scripts/backlog_status.py --json
  ./scripts/hive_ops_run.sh uv run pytest core/tests/test_event_bus.py -q
EOF
  exit 2
fi

DO_BUILD=0
if [[ "${1:-}" == "--build" ]]; then
  DO_BUILD=1
  shift
fi

if [[ $# -eq 0 ]]; then
  echo "error: missing command"
  exit 2
fi

IMAGE_NAME="${HIVE_CORE_IMAGE:-hive-hive-core}"
if [[ "$DO_BUILD" -eq 1 ]] || ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  docker compose build hive-core >/dev/null
fi

# Persistent host-side cache dirs for hive-ops service.
mkdir -p .cache/uv .cache/uvproj

exec docker compose --profile ops run --rm --no-deps hive-ops "$@"

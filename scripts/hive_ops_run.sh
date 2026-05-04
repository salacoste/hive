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

CORE_IMAGE_NAME="${HIVE_CORE_IMAGE:-hive-hive-core}"
OPS_IMAGE_NAME="${HIVE_OPS_IMAGE:-$CORE_IMAGE_NAME}"

build_core_image() {
  docker compose build hive-core >/dev/null
}

build_ops_image() {
  docker compose --profile ops build hive-ops >/dev/null
}

if [[ "$DO_BUILD" -eq 1 ]]; then
  if [[ "$OPS_IMAGE_NAME" == "$CORE_IMAGE_NAME" ]]; then
    build_core_image
  else
    # Keep core image fresh for runtime services and build dedicated ops image.
    build_core_image
    build_ops_image
  fi
else
  if ! docker image inspect "$OPS_IMAGE_NAME" >/dev/null 2>&1; then
    if [[ "$OPS_IMAGE_NAME" == "$CORE_IMAGE_NAME" ]]; then
      build_core_image
    else
      build_ops_image
    fi
  fi
fi

# Persistent host-side cache dirs for hive-ops service.
mkdir -p .cache/uv .cache/uvproj

# Ensure writable ownership for bind/volume mounts used by the non-root
# hiveuser inside hive-ops. Docker named volumes are root-owned on first
# create, which breaks npm/uv writes in container-first flows.
docker compose --profile ops run --rm --no-deps --user root hive-ops sh -lc \
  "mkdir -p /workspace/core/frontend/node_modules /home/hiveuser/.npm /home/hiveuser/.cache/uv /data/uvproj && chown -R 1001:1001 /workspace/core/frontend/node_modules /home/hiveuser/.npm /home/hiveuser/.cache/uv /data/uvproj" \
  >/dev/null

exec docker compose --profile ops run --rm --no-deps hive-ops "$@"

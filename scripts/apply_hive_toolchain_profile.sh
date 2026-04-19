#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/apply_hive_toolchain_profile.sh (--workspace <path> | --repository <url>) [--apply --confirm <token>]

Behavior:
  - Always computes a toolchain plan first (dry-run).
  - By default does not rebuild containers.
  - Apply mode requires explicit confirmation token from plan output.

Examples:
  ./scripts/apply_hive_toolchain_profile.sh --repository https://github.com/salacoste/mcp-n8n-workflow-builder
  ./scripts/apply_hive_toolchain_profile.sh --workspace /path/to/repo --apply --confirm APPLY_NODE_ABC12345
EOF
}

workspace=""
repository=""
apply_mode="false"
confirm_token=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace)
      workspace="${2:-}"
      shift 2
      ;;
    --repository)
      repository="${2:-}"
      shift 2
      ;;
    --apply)
      apply_mode="true"
      shift
      ;;
    --confirm)
      confirm_token="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[fail] unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

if [[ -n "$workspace" && -n "$repository" ]]; then
  echo "[fail] choose only one source: --workspace or --repository"
  exit 2
fi
if [[ -z "$workspace" && -z "$repository" ]]; then
  echo "[fail] one source is required: --workspace or --repository"
  exit 2
fi

detect_args=(--format env)
if [[ -n "$workspace" ]]; then
  detect_args+=(--workspace "$workspace")
else
  detect_args+=(--repository "$repository")
fi

detect_runner=()
if [[ -f "/.dockerenv" ]]; then
  detect_runner=(uv run --no-project python)
elif [[ -x "$ROOT_DIR/scripts/hive_ops_run.sh" ]]; then
  detect_runner=("$ROOT_DIR/scripts/hive_ops_run.sh" uv run --no-project python)
else
  detect_runner=(uv run --no-project python)
fi

plan_env="$("${detect_runner[@]}" scripts/detect_project_toolchains.py "${detect_args[@]}")"

echo "[plan] detected toolchain profile:"
echo "$plan_env"

required_token="$(printf '%s\n' "$plan_env" | awk -F= '/^HIVE_TOOLCHAIN_CONFIRM_TOKEN=/{print $2}')"
if [[ -z "$required_token" ]]; then
  echo "[fail] confirmation token missing in toolchain plan output"
  exit 3
fi

if [[ "$apply_mode" != "true" ]]; then
  echo "[dry-run] no changes applied."
  echo "[next] rerun with: --apply --confirm ${required_token}"
  exit 0
fi

if [[ "$confirm_token" != "$required_token" ]]; then
  echo "[fail] confirmation token mismatch."
  echo "[hint] expected: ${required_token}"
  exit 4
fi

while IFS= read -r line; do
  case "$line" in
    HIVE_DOCKER_INSTALL_*=*)
      export "$line"
      ;;
  esac
done <<<"$plan_env"

echo "[apply] rebuilding Hive images with selected toolchains..."
echo "  HIVE_DOCKER_INSTALL_NODE=${HIVE_DOCKER_INSTALL_NODE:-0}"
echo "  HIVE_DOCKER_INSTALL_GO=${HIVE_DOCKER_INSTALL_GO:-0}"
echo "  HIVE_DOCKER_INSTALL_RUST=${HIVE_DOCKER_INSTALL_RUST:-0}"
echo "  HIVE_DOCKER_INSTALL_JAVA=${HIVE_DOCKER_INSTALL_JAVA:-0}"

docker compose up -d --build hive-core hive-scheduler google-token-refresher

echo "[ok] toolchain profile applied and services recreated."

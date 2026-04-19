#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
PATCH_PATH="${HIVE_UPSTREAM_OVERLAP_PATCH:-docs/ops/upstream-migration/overlap-batch-a-focus-latest.patch}"
MODE="check"
ALLOW_DIRTY="${HIVE_UPSTREAM_ALLOW_DIRTY:-false}"

for arg in "$@"; do
  case "$arg" in
    --check)
      MODE="check"
      ;;
    --apply)
      MODE="apply"
      ;;
    --help|-h)
      cat <<'EOF'
Usage: ./scripts/upstream_overlap_batch_a_apply.sh [--check|--apply]

Environment:
  HIVE_UPSTREAM_LANDING_BRANCH  Expected branch (default: migration/upstream-wave3)
  HIVE_UPSTREAM_OVERLAP_PATCH   Patch path (default: docs/ops/upstream-migration/overlap-batch-a-focus-latest.patch)
  HIVE_UPSTREAM_ALLOW_DIRTY     true/false (default: false)
EOF
      exit 0
      ;;
    *)
      echo "error: unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "${PATCH_PATH}" ]]; then
  echo "error: patch not found: ${PATCH_PATH}" >&2
  exit 1
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "${current_branch}" != "${TARGET_BRANCH}" ]]; then
  echo "error: current branch is '${current_branch}', expected '${TARGET_BRANCH}'" >&2
  exit 1
fi

dirty_count="$(git status --porcelain | wc -l | tr -d ' ')"
if [[ "${ALLOW_DIRTY}" != "true" && "${dirty_count}" != "0" ]]; then
  echo "error: working tree must be clean before apply (dirty_count=${dirty_count})" >&2
  exit 1
fi

echo "== Overlap Batch A Apply =="
echo "mode=${MODE}"
echo "branch=${current_branch}"
echo "patch=${PATCH_PATH}"

git apply --check "${PATCH_PATH}"
echo "[ok] git apply --check passed"

if [[ "${MODE}" == "apply" ]]; then
  git apply "${PATCH_PATH}"
  echo "[ok] patch applied"
  echo "changed files:"
  git status --short
else
  echo "[plan] check-only mode; no changes applied"
fi

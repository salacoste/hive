#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
REPLAY_MANIFEST="docs/ops/upstream-migration/replay-bundle-wave3-latest.md"
DEP_MANIFEST="docs/ops/upstream-migration/overlap-batch-c-dependency-bundle-latest.md"
TOOLS_MANIFEST="docs/ops/upstream-migration/overlap-batch-c-bundle-latest.md"
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
Usage: ./scripts/upstream_overlap_batch_c_bundle_apply.sh [--check|--apply]

Environment:
  HIVE_UPSTREAM_LANDING_BRANCH  Expected branch (default: migration/upstream-wave3)
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

for path in "${REPLAY_MANIFEST}" "${DEP_MANIFEST}" "${TOOLS_MANIFEST}"; do
  if [[ ! -f "${path}" ]]; then
    echo "error: manifest not found: ${path}" >&2
    exit 1
  fi
done

resolve_bundle() {
  local manifest="$1"
  rg -n '^- Bundle: `' "${manifest}" | sed -E 's/.*`([^`]+)`.*/\1/' || true
}

REPLAY_BUNDLE="$(resolve_bundle "${REPLAY_MANIFEST}")"
DEP_BUNDLE="$(resolve_bundle "${DEP_MANIFEST}")"
TOOLS_BUNDLE="$(resolve_bundle "${TOOLS_MANIFEST}")"

for bundle in "${REPLAY_BUNDLE}" "${DEP_BUNDLE}" "${TOOLS_BUNDLE}"; do
  if [[ -z "${bundle}" || ! -f "${bundle}" ]]; then
    echo "error: bundle not found: ${bundle}" >&2
    exit 1
  fi
done

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

echo "== Overlap Batch C Bundle Apply =="
echo "mode=${MODE}"
echo "branch=${current_branch}"
echo "replay_bundle=${REPLAY_BUNDLE}"
echo "dependency_bundle=${DEP_BUNDLE}"
echo "tools_bundle=${TOOLS_BUNDLE}"

if [[ "${MODE}" == "apply" ]]; then
  tar -xzf "${REPLAY_BUNDLE}"
  tar -xzf "${DEP_BUNDLE}"
  tar -xzf "${TOOLS_BUNDLE}"
  echo "[ok] bundles applied"
  echo "changed files:"
  git status --short
else
  echo "[plan] check-only mode; no changes applied"
fi

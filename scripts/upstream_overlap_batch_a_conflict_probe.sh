#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
TARGET_SHA="$(git rev-parse "${TARGET_REF}")"
LANDING_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
PATCH_PATH="docs/ops/upstream-migration/overlap-batch-a-focus-latest.patch"
REPORT_PATH="docs/ops/upstream-migration/overlap-batch-a-conflict-probe-latest.md"
KEEP_CLONE="${HIVE_UPSTREAM_PROBE_KEEP_CLONE:-false}"

if [[ ! -f "${PATCH_PATH}" ]]; then
  echo "error: focus patch not found: ${PATCH_PATH}" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
CLONE_DIR="${TMP_DIR}/repo"

cleanup() {
  if [[ "${KEEP_CLONE}" == "true" ]]; then
    echo "[info] keeping conflict-probe clone: ${CLONE_DIR}"
    return
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

git clone --quiet "${ROOT_DIR}" "${CLONE_DIR}"
cd "${CLONE_DIR}"
git checkout -B "${LANDING_BRANCH}" "${TARGET_SHA}" >/dev/null

APPLY_STATUS="ok"
if ! git apply --3way --index "${ROOT_DIR}/${PATCH_PATH}" >/tmp/hive_overlap_conflicts.log 2>&1; then
  APPLY_STATUS="conflicts"
fi

unmerged_files="$(git diff --name-only --diff-filter=U || true)"
unmerged_count="$(printf "%s\n" "${unmerged_files}" | sed '/^$/d' | wc -l | tr -d ' ')"

{
  echo "# Overlap Batch A Conflict Probe Snapshot"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Target SHA: ${TARGET_SHA}"
  echo "- Landing branch: ${LANDING_BRANCH}"
  echo "- Focus patch: \`${PATCH_PATH}\`"
  echo "- apply mode: \`git apply --3way --index\`"
  echo "- result: ${APPLY_STATUS}"
  echo "- unmerged files: ${unmerged_count}"
  echo
  if [[ -n "${unmerged_files}" ]]; then
    echo "## Unmerged Files"
    echo
    while IFS= read -r f; do
      [[ -z "${f}" ]] && continue
      markers="$(grep -c '^<<<<<<< ' "${f}" || true)"
      echo "- \`${f}\` (conflict markers=${markers})"
    done <<< "${unmerged_files}"
    echo
  fi
  echo "## Raw apply output"
  echo
  echo '```'
  sed -n '1,220p' /tmp/hive_overlap_conflicts.log
  echo '```'
} > "${ROOT_DIR}/${REPORT_PATH}"

echo "[ok] wrote ${REPORT_PATH}"

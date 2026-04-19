#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
TARGET_SHA="$(git rev-parse "${TARGET_REF}")"
LANDING_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
PATCH_PATH="docs/ops/upstream-migration/overlap-batch-a-focus-latest.patch"
REPORT_PATH="docs/ops/upstream-migration/overlap-batch-a-focus-probe-latest.md"
KEEP_CLONE="${HIVE_UPSTREAM_PROBE_KEEP_CLONE:-false}"

if [[ ! -f "${PATCH_PATH}" ]]; then
  echo "error: focus patch not found: ${PATCH_PATH}" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
CLONE_DIR="${TMP_DIR}/repo"

cleanup() {
  if [[ "${KEEP_CLONE}" == "true" ]]; then
    echo "[info] keeping focus-probe clone: ${CLONE_DIR}"
    return
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "== Overlap Batch A Focus Probe =="
echo "target_ref=${TARGET_REF}"
echo "target_sha=${TARGET_SHA}"
echo "landing_branch=${LANDING_BRANCH}"
echo "patch=${PATCH_PATH}"
echo "clone_dir=${CLONE_DIR}"

git clone --quiet "${ROOT_DIR}" "${CLONE_DIR}"
cd "${CLONE_DIR}"

git checkout -B "${LANDING_BRANCH}" "${TARGET_SHA}" >/dev/null
BASE_SHA="$(git rev-parse HEAD)"

CHECK_STATUS="ok"
CHECK_ERROR=""
if ! git apply --check "${ROOT_DIR}/${PATCH_PATH}" 2>/tmp/hive_focus_probe_err.log; then
  CHECK_STATUS="failed"
  CHECK_ERROR="$(cat /tmp/hive_focus_probe_err.log)"
fi

APPLY_STATUS="skipped"
CHANGED_TOTAL="0"
if [[ "${CHECK_STATUS}" == "ok" ]]; then
  git apply "${ROOT_DIR}/${PATCH_PATH}"
  APPLY_STATUS="applied"
  CHANGED_TOTAL="$(git status --short | sed '/^$/d' | wc -l | tr -d ' ')"
fi

{
  echo "# Overlap Batch A Focus Probe Snapshot"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Target SHA: ${TARGET_SHA}"
  echo "- Landing branch: ${LANDING_BRANCH}"
  echo "- Base SHA: ${BASE_SHA}"
  echo "- Focus patch: \`${PATCH_PATH}\`"
  echo "- git apply --check: ${CHECK_STATUS}"
  echo "- apply status: ${APPLY_STATUS}"
  echo "- changed paths after apply: ${CHANGED_TOTAL}"
  if [[ -n "${CHECK_ERROR}" ]]; then
    echo
    echo "## Check Error"
    echo
    echo '```'
    echo "${CHECK_ERROR}"
    echo '```'
  fi
  if [[ "${APPLY_STATUS}" == "applied" ]]; then
    echo
    echo "## git status --short"
    echo
    echo '```'
    git status --short
    echo '```'
  fi
} > "${ROOT_DIR}/${REPORT_PATH}"

echo "[ok] wrote ${REPORT_PATH}"
if [[ "${CHECK_STATUS}" != "ok" ]]; then
  echo "error: focus patch does not apply cleanly" >&2
  exit 1
fi
echo "[ok] focus probe passed"

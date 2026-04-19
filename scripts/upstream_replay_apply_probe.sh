#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
TARGET_SHA="$(git rev-parse "${TARGET_REF}")"
LANDING_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
MANIFEST_PATH="docs/ops/upstream-migration/replay-bundle-wave3-latest.md"
REPORT_PATH="docs/ops/upstream-migration/replay-apply-probe-latest.md"
KEEP_CLONE="${HIVE_UPSTREAM_PROBE_KEEP_CLONE:-false}"

if [[ ! -f "${MANIFEST_PATH}" ]]; then
  echo "error: manifest not found: ${MANIFEST_PATH}" >&2
  exit 1
fi

BUNDLE_PATH="$(rg -n '^- Bundle: `' "${MANIFEST_PATH}" | sed -E 's/.*`([^`]+)`.*/\1/' || true)"
if [[ -z "${BUNDLE_PATH}" ]]; then
  echo "error: bundle path not found in manifest: ${MANIFEST_PATH}" >&2
  exit 1
fi
if [[ ! -f "${BUNDLE_PATH}" ]]; then
  echo "error: bundle file not found: ${BUNDLE_PATH}" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
CLONE_DIR="${TMP_DIR}/repo"

cleanup() {
  if [[ "${KEEP_CLONE}" == "true" ]]; then
    echo "[info] keeping apply-probe clone: ${CLONE_DIR}"
    return
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "== Upstream Replay Apply Probe =="
echo "target_ref=${TARGET_REF}"
echo "target_sha=${TARGET_SHA}"
echo "landing_branch=${LANDING_BRANCH}"
echo "bundle=${BUNDLE_PATH}"
echo "clone_dir=${CLONE_DIR}"

git clone --quiet "${ROOT_DIR}" "${CLONE_DIR}"
cd "${CLONE_DIR}"

git checkout -B "${LANDING_BRANCH}" "${TARGET_SHA}" >/dev/null
BASE_SHA="$(git rev-parse HEAD)"

tar -xzf "${ROOT_DIR}/${BUNDLE_PATH}" -C "${CLONE_DIR}"

STATUS_SHORT="$(git status --short)"
CHANGED_TOTAL="$(echo "${STATUS_SHORT}" | sed '/^$/d' | wc -l | tr -d ' ')"
MODIFIED_TOTAL="$(printf "%s\n" "${STATUS_SHORT}" | awk '/^[ MARC][MD]/ {c++} END {print c+0}')"
UNTRACKED_TOTAL="$(printf "%s\n" "${STATUS_SHORT}" | awk '/^\?\?/ {c++} END {print c+0}')"

{
  echo "# Replay Apply Probe Snapshot (Wave 3)"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Target SHA: ${TARGET_SHA}"
  echo "- Landing branch: ${LANDING_BRANCH}"
  echo "- Base SHA before apply: ${BASE_SHA}"
  echo "- Bundle: \`${BUNDLE_PATH}\`"
  echo "- Changed paths after apply: ${CHANGED_TOTAL}"
  echo "- Modified/tracked paths: ${MODIFIED_TOTAL}"
  echo "- Untracked paths: ${UNTRACKED_TOTAL}"
  echo
  echo "## git status --short"
  echo
  echo '```'
  if [[ -n "${STATUS_SHORT}" ]]; then
    echo "${STATUS_SHORT}"
  fi
  echo '```'
} > "${ROOT_DIR}/${REPORT_PATH}"

echo "[ok] wrote ${REPORT_PATH}"
echo "[ok] apply probe completed"

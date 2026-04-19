#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
TARGET_SHA="$(git rev-parse "${TARGET_REF}")"
LANDING_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
REPORT_PATH="docs/ops/upstream-migration/overlap-batch-a-file-probe-latest.md"
KEEP_CLONE="${HIVE_UPSTREAM_PROBE_KEEP_CLONE:-false}"

files=(
  "core/framework/server/app.py"
  "core/framework/server/routes_execution.py"
  "core/framework/server/routes_sessions.py"
  "core/framework/server/session_manager.py"
  "core/framework/server/queen_orchestrator.py"
  "core/framework/server/routes_credentials.py"
)

TMP_DIR="$(mktemp -d)"
CLONE_DIR="${TMP_DIR}/repo"

cleanup() {
  if [[ "${KEEP_CLONE}" == "true" ]]; then
    echo "[info] keeping file-probe clone: ${CLONE_DIR}"
    return
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

git clone --quiet "${ROOT_DIR}" "${CLONE_DIR}"
cd "${CLONE_DIR}"
git checkout -B "${LANDING_BRANCH}" "${TARGET_SHA}" >/dev/null

{
  echo "# Overlap Batch A File Probe"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Target SHA: ${TARGET_SHA}"
  echo "- Landing branch: ${LANDING_BRANCH}"
  echo
  echo "| File | apply --check | Added | Removed |"
  echo "|---|---|---:|---:|"

  for f in "${files[@]}"; do
    patch_file="${TMP_DIR}/$(basename "${f}").patch"
    git -C "${ROOT_DIR}" diff --no-color "${TARGET_REF}" -- "${f}" > "${patch_file}"

    if [[ ! -s "${patch_file}" ]]; then
      echo "| \`${f}\` | no-diff | 0 | 0 |"
      continue
    fi

    git reset --hard "${TARGET_SHA}" >/dev/null
    git clean -fd >/dev/null

    if git apply --check "${patch_file}" >/dev/null 2>&1; then
      git apply "${patch_file}"
      ns="$(git diff --numstat -- "${f}" | head -n 1 || true)"
      add="0"
      del="0"
      if [[ -n "${ns}" ]]; then
        add="$(echo "${ns}" | awk '{print $1}')"
        del="$(echo "${ns}" | awk '{print $2}')"
      fi
      echo "| \`${f}\` | ok | ${add} | ${del} |"
    else
      echo "| \`${f}\` | failed | - | - |"
    fi
  done
} > "${ROOT_DIR}/${REPORT_PATH}"

echo "[ok] wrote ${REPORT_PATH}"

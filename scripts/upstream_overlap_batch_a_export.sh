#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
OUT_DIR="docs/ops/upstream-migration"
PATCH_PATH="${OUT_DIR}/overlap-batch-a-latest.patch"
SUMMARY_PATH="${OUT_DIR}/overlap-batch-a-latest.md"

files=(
  "core/framework/server/app.py"
  "core/framework/server/routes_execution.py"
  "core/framework/server/routes_sessions.py"
  "core/framework/server/queen_orchestrator.py"
  "core/framework/server/routes_credentials.py"
  "core/framework/server/session_manager.py"
  "core/framework/server/tests/test_api.py"
  "core/framework/server/tests/test_queen_orchestrator.py"
)

mkdir -p "${OUT_DIR}"

git diff --no-color "${TARGET_REF}" -- "${files[@]}" > "${PATCH_PATH}"

{
  echo "# Overlap Batch A Export"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Patch: \`${PATCH_PATH}\`"
  echo
  echo "## Files"
  echo
  for f in "${files[@]}"; do
    echo "- \`${f}\`"
  done
  echo
  echo "## Numstat vs ${TARGET_REF}"
  echo
  echo "| File | + | - |"
  echo "|---|---:|---:|"
  git diff --numstat "${TARGET_REF}" -- "${files[@]}" | while IFS=$'\t' read -r add del path; do
    [[ -z "${path:-}" ]] && continue
    echo "| \`${path}\` | ${add:-0} | ${del:-0} |"
  done
} > "${SUMMARY_PATH}"

echo "[ok] wrote ${PATCH_PATH}"
echo "[ok] wrote ${SUMMARY_PATH}"

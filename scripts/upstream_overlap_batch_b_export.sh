#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
PATCH_PATH="docs/ops/upstream-migration/overlap-batch-b-latest.patch"
REPORT_PATH="docs/ops/upstream-migration/overlap-batch-b-latest.md"

FILES=(
  "core/frontend/src/pages/workspace.tsx"
  "core/frontend/src/pages/my-agents.tsx"
  "core/frontend/src/components/HistorySidebar.tsx"
  "core/frontend/src/api/types.ts"
  "core/frontend/src/api/sessions.ts"
  "core/frontend/src/api/execution.ts"
  "core/frontend/src/api/credentials.ts"
  "core/frontend/src/lib/chat-helpers.ts"
  "core/frontend/src/lib/chat-helpers.test.ts"
)

mkdir -p "docs/ops/upstream-migration"

git diff --no-color "${TARGET_REF}" -- "${FILES[@]}" > "${PATCH_PATH}"

LINE_COUNT="$(wc -l < "${PATCH_PATH}" | tr -d ' ')"
BYTE_COUNT="$(wc -c < "${PATCH_PATH}" | tr -d ' ')"
FILE_COUNT="$(printf '%s\n' "${FILES[@]}" | wc -l | tr -d ' ')"
NUMSTAT="$(git diff --numstat "${TARGET_REF}" -- "${FILES[@]}" || true)"

{
  echo "# Overlap Batch B Export"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Files in scope: ${FILE_COUNT}"
  echo "- Patch: \`${PATCH_PATH}\`"
  echo "- Patch lines: ${LINE_COUNT}"
  echo "- Patch bytes: ${BYTE_COUNT}"
  echo
  echo "## Files"
  echo
  for file in "${FILES[@]}"; do
    echo "- \`${file}\`"
  done
  echo
  echo "## Numstat"
  echo
  echo '```'
  if [[ -n "${NUMSTAT}" ]]; then
    echo "${NUMSTAT}"
  fi
  echo '```'
} > "${REPORT_PATH}"

echo "[ok] wrote ${PATCH_PATH}"
echo "[ok] wrote ${REPORT_PATH}"

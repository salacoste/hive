#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
PATCH_PATH="docs/ops/upstream-migration/overlap-batch-c-latest.patch"
REPORT_PATH="docs/ops/upstream-migration/overlap-batch-c-latest.md"

FILES=(
  "tools/Dockerfile"
  "tools/coder_tools_server.py"
  "tools/mcp_servers.json"
  "tools/src/aden_tools/credentials/__init__.py"
  "tools/src/aden_tools/tools/__init__.py"
  "tools/src/aden_tools/tools/calendar_tool/calendar_tool.py"
  "tools/src/aden_tools/tools/github_tool/github_tool.py"
  "tools/src/aden_tools/tools/gmail_tool/gmail_tool.py"
  "tools/src/aden_tools/tools/google_docs_tool/google_docs_tool.py"
  "tools/src/aden_tools/tools/google_sheets_tool/google_sheets_tool.py"
  "tools/src/gcu/__init__.py"
  "tools/tests/test_coder_tools_server.py"
  "tools/tests/tools/test_github_tool.py"
)

mkdir -p "docs/ops/upstream-migration"

git diff --no-color "${TARGET_REF}" -- "${FILES[@]}" > "${PATCH_PATH}"

LINE_COUNT="$(wc -l < "${PATCH_PATH}" | tr -d ' ')"
BYTE_COUNT="$(wc -c < "${PATCH_PATH}" | tr -d ' ')"
FILE_COUNT="$(printf '%s\n' "${FILES[@]}" | wc -l | tr -d ' ')"
NUMSTAT="$(git diff --numstat "${TARGET_REF}" -- "${FILES[@]}" || true)"

{
  echo "# Overlap Batch C Export"
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

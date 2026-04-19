#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
OUT_DIR="docs/ops/upstream-migration/replay-bundles"
LATEST_MANIFEST="docs/ops/upstream-migration/overlap-batch-c-bundle-latest.md"
TIMESTAMP="$(date -u +"%Y%m%d-%H%M%S")"
BUNDLE_PATH="${OUT_DIR}/wave3-batch-c-tools-${TIMESTAMP}.tar.gz"

INCLUDE_FILES=(
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

for path in "${INCLUDE_FILES[@]}"; do
  if [[ ! -f "${path}" ]]; then
    echo "error: missing tools overlap file: ${path}" >&2
    exit 1
  fi
done

mkdir -p "${OUT_DIR}"
tar -czf "${BUNDLE_PATH}" "${INCLUDE_FILES[@]}"

if command -v shasum >/dev/null 2>&1; then
  CHECKSUM="$(shasum -a 256 "${BUNDLE_PATH}" | awk '{print $1}')"
elif command -v sha256sum >/dev/null 2>&1; then
  CHECKSUM="$(sha256sum "${BUNDLE_PATH}" | awk '{print $1}')"
else
  CHECKSUM="unavailable"
fi

NUMSTAT="$(git diff --numstat "${TARGET_REF}" -- "${INCLUDE_FILES[@]}" || true)"

{
  echo "# Overlap Batch C Bundle (Latest)"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref (informational): \`${TARGET_REF}\`"
  echo "- Bundle: \`${BUNDLE_PATH}\`"
  echo "- SHA256: \`${CHECKSUM}\`"
  echo "- Included file count: \`13\`"
  echo
  echo "## Included files"
  echo
  for path in "${INCLUDE_FILES[@]}"; do
    echo "- \`${path}\`"
  done
  echo
  echo "## Numstat vs ${TARGET_REF}"
  echo
  echo "| File | + | - |"
  echo "|---|---:|---:|"
  while IFS=$'\t' read -r add del path; do
    [[ -z "${path:-}" ]] && continue
    echo "| \`${path}\` | ${add:-0} | ${del:-0} |"
  done <<<"${NUMSTAT}"
  echo
  echo "## Apply in clean probe/landing clone"
  echo
  echo '```bash'
  echo "tar -xzf ${BUNDLE_PATH}"
  echo '```'
} > "${LATEST_MANIFEST}"

echo "[ok] wrote ${BUNDLE_PATH}"
echo "[ok] wrote ${LATEST_MANIFEST}"

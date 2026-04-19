#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
OUT_DIR="docs/ops/upstream-migration/replay-bundles"
LATEST_MANIFEST="docs/ops/upstream-migration/overlap-batch-b-bundle-latest.md"
TIMESTAMP="$(date -u +"%Y%m%d-%H%M%S")"
BUNDLE_PATH="${OUT_DIR}/wave3-batch-b-frontend-${TIMESTAMP}.tar.gz"

INCLUDE_FILES=(
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

for path in "${INCLUDE_FILES[@]}"; do
  if [[ ! -f "${path}" ]]; then
    echo "error: missing frontend overlap file: ${path}" >&2
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
  echo "# Overlap Batch B Frontend Bundle (Latest)"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref (informational): \`${TARGET_REF}\`"
  echo "- Bundle: \`${BUNDLE_PATH}\`"
  echo "- SHA256: \`${CHECKSUM}\`"
  echo "- Included file count: \`9\`"
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

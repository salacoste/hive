#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
OUT_DIR="docs/ops/upstream-migration/replay-bundles"
LATEST_MANIFEST="docs/ops/upstream-migration/overlap-batch-b-dependency-bundle-latest.md"
TIMESTAMP="$(date -u +"%Y%m%d-%H%M%S")"
BUNDLE_PATH="${OUT_DIR}/wave3-batch-b-dependency-${TIMESTAMP}.tar.gz"

INCLUDE_PATHS=(
  "core/frontend/src/components"
  "core/frontend/src/lib"
  "core/frontend/src/hooks"
  "core/frontend/src/api/agents.ts"
  "core/frontend/src/api/client.ts"
  "core/frontend/src/api/graphs.ts"
  "core/frontend/src/api/logs.ts"
)

for path in "${INCLUDE_PATHS[@]}"; do
  if [[ ! -e "${path}" ]]; then
    echo "error: missing frontend dependency path: ${path}" >&2
    exit 1
  fi
done

mkdir -p "${OUT_DIR}"
tar -czf "${BUNDLE_PATH}" "${INCLUDE_PATHS[@]}"

if command -v shasum >/dev/null 2>&1; then
  CHECKSUM="$(shasum -a 256 "${BUNDLE_PATH}" | awk '{print $1}')"
elif command -v sha256sum >/dev/null 2>&1; then
  CHECKSUM="$(sha256sum "${BUNDLE_PATH}" | awk '{print $1}')"
else
  CHECKSUM="unavailable"
fi

FILE_COUNT="$(
  {
    find core/frontend/src/components -type f 2>/dev/null || true
    find core/frontend/src/lib -type f 2>/dev/null || true
    find core/frontend/src/hooks -type f 2>/dev/null || true
    printf '%s\n' core/frontend/src/api/agents.ts
    printf '%s\n' core/frontend/src/api/client.ts
    printf '%s\n' core/frontend/src/api/graphs.ts
    printf '%s\n' core/frontend/src/api/logs.ts
  } | sed '/^$/d' | wc -l | tr -d ' '
)"

{
  echo "# Overlap Batch B Dependency Bundle (Latest)"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref (informational): \`${TARGET_REF}\`"
  echo "- Bundle: \`${BUNDLE_PATH}\`"
  echo "- SHA256: \`${CHECKSUM}\`"
  echo "- Included file count: \`${FILE_COUNT}\`"
  echo
  echo "## Included roots"
  echo
  for path in "${INCLUDE_PATHS[@]}"; do
    echo "- \`${path}\`"
  done
  echo
  echo "## Apply in clean probe/landing clone"
  echo
  echo '```bash'
  echo "tar -xzf ${BUNDLE_PATH}"
  echo '```'
} > "${LATEST_MANIFEST}"

echo "[ok] wrote ${BUNDLE_PATH}"
echo "[ok] wrote ${LATEST_MANIFEST}"

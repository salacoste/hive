#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
OUT_DIR="docs/ops/upstream-migration/replay-bundles"
LATEST_MANIFEST="docs/ops/upstream-migration/overlap-batch-c-dependency-bundle-latest.md"
TIMESTAMP="$(date -u +"%Y%m%d-%H%M%S")"
BUNDLE_PATH="${OUT_DIR}/wave3-batch-c-dependency-${TIMESTAMP}.tar.gz"

INCLUDE_PATHS=(
  "tools/src/aden_tools"
  "tools/src/gcu"
  "tools/tests"
  "tools/pyproject.toml"
  "tools/uv.lock"
  "scripts/mcp_health_summary.py"
)

for path in "${INCLUDE_PATHS[@]}"; do
  if [[ ! -e "${path}" ]]; then
    echo "error: missing tools dependency path: ${path}" >&2
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
    find tools/src/aden_tools -type f 2>/dev/null || true
    find tools/src/gcu -type f 2>/dev/null || true
    find tools/tests -type f 2>/dev/null || true
    printf '%s\n' tools/pyproject.toml
    printf '%s\n' tools/uv.lock
    printf '%s\n' scripts/mcp_health_summary.py
  } | sed '/^$/d' | wc -l | tr -d ' '
)"

{
  echo "# Overlap Batch C Dependency Bundle (Latest)"
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

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
MANIFEST_PATH="docs/ops/upstream-migration/replay-bundle-wave3-latest.md"
REPORT_PATH="docs/ops/upstream-migration/replay-bundle-wave3-compat-latest.md"

if [[ ! -f "${MANIFEST_PATH}" ]]; then
  echo "error: manifest not found: ${MANIFEST_PATH}" >&2
  exit 1
fi

paths=()
while IFS= read -r line; do
  paths+=("${line}")
done < <(rg -o '^- `([^`]+)`$' "${MANIFEST_PATH}" -r '$1')

if [[ "${#paths[@]}" -eq 0 ]]; then
  echo "error: no paths found in manifest" >&2
  exit 1
fi

overlay=0
add=0

{
  echo "# Replay Bundle Compatibility Report (Wave 3)"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Source manifest: \`${MANIFEST_PATH}\`"
  echo
  echo "| Path | Action on ${TARGET_REF} |"
  echo "|---|---|"

  for p in "${paths[@]}"; do
    if git cat-file -e "${TARGET_REF}:${p}" 2>/dev/null; then
      echo "| \`${p}\` | \`overlay\` |"
      overlay=$((overlay + 1))
    else
      echo "| \`${p}\` | \`add\` |"
      add=$((add + 1))
    fi
  done

  echo
  echo "## Summary"
  echo
  echo "- paths total: $((overlay + add))"
  echo "- overlay: ${overlay}"
  echo "- add: ${add}"
} > "${REPORT_PATH}"

echo "[ok] wrote ${REPORT_PATH}"

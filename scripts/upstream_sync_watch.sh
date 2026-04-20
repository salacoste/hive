#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

BASE_REF="${HIVE_UPSTREAM_BASE_REF:-origin/main}"
TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-upstream/main}"
FAIL_IF_BEHIND="${HIVE_UPSTREAM_FAIL_IF_BEHIND:-0}"
OUTPUT_PATH=""
JSON_PATH=""

usage() {
  cat <<'EOF'
Usage: ./scripts/upstream_sync_watch.sh [--output <path>] [--json <path>]

Options:
  --output <path>   Write markdown report to path.
  --json <path>     Write machine-readable JSON summary to path.

Environment:
  HIVE_UPSTREAM_BASE_REF      Base ref (default: origin/main)
  HIVE_UPSTREAM_TARGET_REF    Target ref (default: upstream/main)
  HIVE_UPSTREAM_FAIL_IF_BEHIND  If "1", exit non-zero when base is behind target.
EOF
}

while (($#)); do
  case "$1" in
    --output)
      OUTPUT_PATH="${2:-}"
      shift 2
      ;;
    --json)
      JSON_PATH="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument '$1'" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "${FAIL_IF_BEHIND}" =~ ^[01]$ ]]; then
  echo "error: HIVE_UPSTREAM_FAIL_IF_BEHIND must be 0 or 1" >&2
  exit 2
fi

git rev-parse --verify "${BASE_REF}" >/dev/null
git rev-parse --verify "${TARGET_REF}" >/dev/null

counts="$(git rev-list --left-right --count "${BASE_REF}...${TARGET_REF}")"
read -r base_only target_only <<<"${counts}"
merge_base="$(git merge-base "${BASE_REF}" "${TARGET_REF}")"
base_sha="$(git rev-parse "${BASE_REF}")"
target_sha="$(git rev-parse "${TARGET_REF}")"
generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

delta_json="$(mktemp)"
uv run python scripts/upstream_delta_status.py \
  --base-ref "${BASE_REF}" \
  --target-ref "${TARGET_REF}" \
  --json > "${delta_json}"

changes_preview="$(mktemp)"
git diff --name-status "${BASE_REF}..${TARGET_REF}" | head -n 120 > "${changes_preview}" || true

if [[ -n "${JSON_PATH}" ]]; then
  mkdir -p "$(dirname "${JSON_PATH}")"
  uv run --no-project python - "${delta_json}" "${JSON_PATH}" "${BASE_REF}" "${TARGET_REF}" "${base_sha}" "${target_sha}" "${merge_base}" "${generated_at}" "${base_only}" "${target_only}" <<'PY'
import json
import sys
from pathlib import Path

delta_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
base_ref, target_ref, base_sha, target_sha, merge_base, generated_at = sys.argv[3:9]
base_only = int(sys.argv[9])
target_only = int(sys.argv[10])

delta = json.loads(delta_path.read_text(encoding="utf-8"))
payload = {
    "generated_at": generated_at,
    "base_ref": base_ref,
    "target_ref": target_ref,
    "base_sha": base_sha,
    "target_sha": target_sha,
    "merge_base": merge_base,
    "ahead_by": base_only,
    "behind_by": target_only,
    "delta_buckets": delta.get("buckets", {}),
}
out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(str(out_path))
PY
fi

if [[ -n "${OUTPUT_PATH}" ]]; then
  mkdir -p "$(dirname "${OUTPUT_PATH}")"
  uv run --no-project python - "${delta_json}" "${changes_preview}" "${OUTPUT_PATH}" "${BASE_REF}" "${TARGET_REF}" "${base_sha}" "${target_sha}" "${merge_base}" "${generated_at}" "${base_only}" "${target_only}" <<'PY'
import json
import sys
from pathlib import Path

delta_path = Path(sys.argv[1])
preview_path = Path(sys.argv[2])
output_path = Path(sys.argv[3])
base_ref, target_ref, base_sha, target_sha, merge_base, generated_at = sys.argv[4:10]
base_only = int(sys.argv[10])
target_only = int(sys.argv[11])

delta = json.loads(delta_path.read_text(encoding="utf-8"))
buckets = delta.get("buckets", {})

def bucket_count(name: str) -> int:
    payload = buckets.get(name, {})
    if isinstance(payload, dict):
        return int(payload.get("count", 0))
    return 0

preview = preview_path.read_text(encoding="utf-8").strip()
if not preview:
    preview = "(no changed files)"

report = f"""# Upstream Sync Watch Report

Generated: {generated_at}

Base: `{base_ref}` (`{base_sha}`)
Target: `{target_ref}` (`{target_sha}`)
Merge-base: `{merge_base}`

## Drift Summary

- Ahead (base-only commits): `{base_only}`
- Behind (target-only commits): `{target_only}`

## Bucket Summary

- Bucket A (low risk): `{bucket_count("bucket_a_low_risk")}`
- Bucket B (medium risk): `{bucket_count("bucket_b_medium_risk")}`
- Bucket C (high risk): `{bucket_count("bucket_c_high_risk")}`
- Unclassified: `{bucket_count("other_unclassified")}`

## Changed Files Preview (`{base_ref}..{target_ref}`)

```text
{preview}
```
"""
output_path.write_text(report, encoding="utf-8")
print(str(output_path))
PY
fi

echo "== Upstream Sync Watch =="
echo "base_ref=${BASE_REF} (${base_sha})"
echo "target_ref=${TARGET_REF} (${target_sha})"
echo "merge_base=${merge_base}"
echo "ahead_by=${base_only}"
echo "behind_by=${target_only}"

if [[ "${FAIL_IF_BEHIND}" == "1" && "${target_only}" -gt 0 ]]; then
  echo "error: base is behind target by ${target_only} commit(s)" >&2
  exit 1
fi

echo "[ok] upstream sync watch completed"

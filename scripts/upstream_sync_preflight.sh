#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TARGET_REF="${1:-origin/main}"

echo "== Upstream Sync Preflight =="
echo "target_ref=${TARGET_REF}"

echo
echo "-- backlog structure --"
uv run python scripts/validate_backlog_markdown.py
uv run python scripts/backlog_status.py --path docs/autonomous-factory/12-backlog-task-list.md

echo
echo "-- backlog consistency --"
uv run python scripts/check_backlog_status_consistency.py

echo
echo "-- upstream delta counts --"
git rev-list --left-right --count "HEAD...${TARGET_REF}"

echo
echo "-- upstream changed files --"
git diff --name-status "HEAD..${TARGET_REF}" || true

echo
echo "-- destructive lane guardrail --"
uv run python scripts/check_upstream_destructive_lanes.py --base-ref HEAD --upstream-ref "${TARGET_REF}"

echo
echo "-- hotspot overlap (local dirty files) --"
DIRTY_FILES="$(git status --porcelain | awk '{print $2}' || true)"
if [[ -n "${DIRTY_FILES}" ]]; then
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if git diff --name-only "HEAD..${TARGET_REF}" | rg -Fxq "$f"; then
      echo "hotspot: $f"
    fi
  done <<< "${DIRTY_FILES}"
else
  echo "none"
fi

echo
echo "-- upstream delta buckets --"
uv run python scripts/upstream_delta_status.py --base-ref HEAD --target-ref "${TARGET_REF}"

echo
echo "-- upstream bucket contract sync --"
uv run python scripts/check_upstream_bucket_contract_sync.py

echo
echo "-- unclassified decision coverage --"
uv run python scripts/check_unclassified_delta_decisions.py

echo
echo "-- unclassified decision report sync --"
uv run python scripts/render_unclassified_decision_report.py --check docs/ops/upstream-unclassified-decisions.md

echo
echo "[ok] upstream preflight completed"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${HIVE_OPS_PREFLIGHT_BASE_URL:-http://hive-core:8787}"
BACKLOG_KEEP="${HIVE_OPS_PREFLIGHT_BACKLOG_KEEP:-50}"
BACKLOG_HYGIENE_APPLY="${HIVE_OPS_PREFLIGHT_BACKLOG_HYGIENE_APPLY:-1}"
BUILD_OPS_IMAGE="${HIVE_OPS_PREFLIGHT_BUILD_IMAGE:-0}"

run_step() {
  local label="$1"
  shift
  echo
  echo "== $label =="
  "$@"
}

OPS_RUN=(./scripts/hive_ops_run.sh)
if [[ "$BUILD_OPS_IMAGE" == "1" ]]; then
  OPS_RUN+=(--build)
fi

run_step "Backlog validation" \
  "${OPS_RUN[@]}" uv run --no-project python scripts/validate_backlog_markdown.py
run_step "Backlog status (json)" \
  "${OPS_RUN[@]}" uv run --no-project python scripts/backlog_status.py --json
run_step "Docs/runbook sync checks" \
  "${OPS_RUN[@]}" uv run --no-project python scripts/check_acceptance_docs_navigation.py
run_step "Runbook sync contract" \
  "${OPS_RUN[@]}" uv run --no-project python scripts/check_runbook_sync.py
run_step "Upstream bucket contract" \
  "${OPS_RUN[@]}" uv run --no-project python scripts/check_upstream_bucket_contract_sync.py
run_step "Unclassified decision coverage" \
  "${OPS_RUN[@]}" uv run --no-project python scripts/check_unclassified_delta_decisions.py
run_step "Unclassified report sync" \
  "${OPS_RUN[@]}" uv run --no-project python scripts/render_unclassified_decision_report.py --check docs/ops/upstream-unclassified-decisions.md
run_step "Runtime parity (container network)" \
  "${OPS_RUN[@]}" sh -lc "HIVE_BASE_URL=${BASE_URL} ./scripts/check_runtime_parity.sh"
run_step "Backlog status artifact refresh" \
  "${OPS_RUN[@]}" uv run --no-project python scripts/backlog_status_artifact.py

if [[ "$BACKLOG_HYGIENE_APPLY" == "1" ]]; then
  run_step "Backlog status hygiene apply" \
    "${OPS_RUN[@]}" uv run --no-project python scripts/backlog_status_hygiene.py --keep "$BACKLOG_KEEP" --yes
else
  run_step "Backlog status hygiene preview" \
    "${OPS_RUN[@]}" uv run --no-project python scripts/backlog_status_hygiene.py --keep "$BACKLOG_KEEP"
fi

echo
echo "[ok] hive ops preflight completed"

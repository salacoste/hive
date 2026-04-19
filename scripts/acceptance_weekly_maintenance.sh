#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DAYS="${HIVE_ACCEPTANCE_DIGEST_DAYS:-7}"
LIMIT="${HIVE_ACCEPTANCE_DIGEST_LIMIT:-20}"
KEEP="${HIVE_ACCEPTANCE_REPORT_KEEP:-50}"
APPLY_PRUNE="${HIVE_ACCEPTANCE_REPORT_PRUNE_APPLY:-false}"
ENFORCE_HISTORY="${HIVE_ACCEPTANCE_ENFORCE_HISTORY:-true}"
MAX_FAIL="${HIVE_ACCEPTANCE_HISTORY_MAX_FAIL:-0}"
MIN_PASS_RATE="${HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE:-1.0}"
OUT_JSON="${HIVE_ACCEPTANCE_DIGEST_JSON_PATH:-docs/ops/acceptance-reports/digest-latest.json}"
OUT_MD="${HIVE_ACCEPTANCE_DIGEST_MD_PATH:-docs/ops/acceptance-reports/digest-latest.md}"

ok=0
failed=0

run_step() {
  local name="$1"
  shift
  if "$@"; then
    echo "[ok] $name"
    ok=$((ok + 1))
  else
    echo "[fail] $name" >&2
    failed=$((failed + 1))
  fi
}

echo "== Acceptance Weekly Maintenance =="
echo "days=$DAYS limit=$LIMIT keep=$KEEP apply_prune=$APPLY_PRUNE enforce_history=$ENFORCE_HISTORY"

run_step "acceptance report digest" \
  uv run python scripts/acceptance_report_digest.py \
    --days "$DAYS" \
    --limit "$LIMIT" \
    --out-json "$OUT_JSON" \
    --out-md "$OUT_MD"

if [[ "$APPLY_PRUNE" == "true" ]]; then
  run_step "acceptance report hygiene (apply)" \
    uv run python scripts/acceptance_report_hygiene.py --keep "$KEEP" --yes
else
  run_step "acceptance report hygiene (preview)" \
    uv run python scripts/acceptance_report_hygiene.py --keep "$KEEP"
fi

if [[ "$ENFORCE_HISTORY" == "true" ]]; then
  run_step "acceptance regression guard" \
    uv run python scripts/acceptance_report_regression_guard.py \
      --days "$DAYS" \
      --max-fail "$MAX_FAIL" \
      --min-pass-rate "$MIN_PASS_RATE"
else
  echo "[skip] acceptance regression guard"
fi

echo "== Weekly maintenance summary: ok=$ok failed=$failed =="
if [[ "$failed" -gt 0 ]]; then
  exit 1
fi

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== Acceptance Preset Smoke Determinism Check =="

output=$(
  HIVE_ACCEPTANCE_ENFORCE_HISTORY=true \
  HIVE_ACCEPTANCE_SUMMARY_JSON=true \
  HIVE_ACCEPTANCE_RUN_SELF_CHECK=true \
  HIVE_ACCEPTANCE_RUN_DOCS_NAV_CHECK=true \
  HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=true \
  HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=true \
  HIVE_DELIVERY_E2E_SKIP_REAL=true \
  HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true \
  HIVE_ACCEPTANCE_SKIP_TELEGRAM=true \
  ./scripts/acceptance_gate_presets_smoke.sh
)

printf '%s\n' "$output"

fast_block="$(printf '%s\n' "$output" | sed -n '/mode=fast/,/\[ok\] preset fast print-only/p')"
strict_block="$(printf '%s\n' "$output" | sed -n '/mode=strict/,/\[ok\] preset strict print-only/p' | head -n 40)"
full_deep_block="$(printf '%s\n' "$output" | sed -n '/mode=full-deep/,/\[ok\] preset full-deep print-only/p')"

fail=0

if ! printf '%s\n' "$fast_block" | grep -q 'HIVE_ACCEPTANCE_ENFORCE_HISTORY=$'; then
  echo "[fail] fast mode leaked ENFORCE_HISTORY" >&2
  fail=$((fail + 1))
fi
if ! printf '%s\n' "$fast_block" | grep -q 'HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=$'; then
  echo "[fail] fast mode leaked RUN_PRESET_SMOKE" >&2
  fail=$((fail + 1))
fi
if ! printf '%s\n' "$fast_block" | grep -q 'HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=$'; then
  echo "[fail] fast mode leaked RUN_DELIVERY_E2E_SMOKE" >&2
  fail=$((fail + 1))
fi
if ! printf '%s\n' "$fast_block" | grep -q 'HIVE_DELIVERY_E2E_SKIP_REAL=$'; then
  echo "[fail] fast mode leaked DELIVERY_E2E_SKIP_REAL" >&2
  fail=$((fail + 1))
fi
if ! printf '%s\n' "$strict_block" | grep -q 'HIVE_ACCEPTANCE_RUN_SELF_CHECK=$'; then
  echo "[fail] strict mode leaked RUN_SELF_CHECK" >&2
  fail=$((fail + 1))
fi
if ! printf '%s\n' "$full_deep_block" | grep -q 'HIVE_ACCEPTANCE_RUN_PRESET_SMOKE=true$'; then
  echo "[fail] full-deep mode lost RUN_PRESET_SMOKE=true" >&2
  fail=$((fail + 1))
fi
if ! printf '%s\n' "$full_deep_block" | grep -q 'HIVE_ACCEPTANCE_RUN_DELIVERY_E2E_SMOKE=true$'; then
  echo "[fail] full-deep mode lost RUN_DELIVERY_E2E_SMOKE=true" >&2
  fail=$((fail + 1))
fi
if ! printf '%s\n' "$full_deep_block" | grep -q 'HIVE_DELIVERY_E2E_SKIP_REAL=true$'; then
  echo "[fail] full-deep mode lost DELIVERY_E2E_SKIP_REAL=true" >&2
  fail=$((fail + 1))
fi
if ! printf '%s\n' "$full_deep_block" | grep -q 'HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true$'; then
  echo "[fail] full-deep mode lost SELF_CHECK_RUN_RUNTIME_PARITY=true" >&2
  fail=$((fail + 1))
fi

if [[ "$fail" -gt 0 ]]; then
  echo "[fail] acceptance preset smoke determinism check failed: $fail" >&2
  exit 1
fi

echo "[ok] acceptance preset smoke determinism is stable"

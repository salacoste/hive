#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

MODE="create"
WAVE="${HIVE_UPSTREAM_REPLAY_WAVE:-wave3}"
BUNDLE_DIR="docs/ops/upstream-migration/replay-bundles"
LATEST_MANIFEST="docs/ops/upstream-migration/replay-bundle-${WAVE}-latest.md"
TS="$(date -u +"%Y%m%d-%H%M%S")"
BUNDLE_PATH="${BUNDLE_DIR}/${WAVE}-${TS}.tar.gz"

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      MODE="dry-run"
      ;;
    --create)
      MODE="create"
      ;;
    --help|-h)
      cat <<'EOF'
Usage: ./scripts/upstream_replay_bundle.sh [--dry-run|--create]

Builds a replay bundle for upstream migration wave control-plane modules.
EOF
      exit 0
      ;;
    *)
      echo "error: unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

paths=(
  "core/framework/server/project_execution.py"
  "core/framework/server/project_metrics.py"
  "core/framework/server/project_onboarding.py"
  "core/framework/server/project_policy.py"
  "core/framework/server/project_retention.py"
  "core/framework/server/project_store.py"
  "core/framework/server/project_templates.py"
  "core/framework/server/project_toolchain.py"
  "core/framework/server/routes_projects.py"
  "core/framework/server/routes_autonomous.py"
  "core/framework/server/telegram_bridge.py"
  "core/framework/server/autonomous_pipeline.py"
  "core/frontend/src/api/projects.ts"
  "core/frontend/src/api/autonomous.ts"
  "docs/LOCAL_PROD_RUNBOOK.md"
  "docs/autonomous-factory"
  "scripts/autonomous_acceptance_gate.sh"
  "scripts/autonomous_delivery_e2e_smoke.py"
  "scripts/autonomous_loop_tick.sh"
  "scripts/autonomous_operator_profile.sh"
  "scripts/autonomous_ops_drill.sh"
  "scripts/autonomous_ops_health_check.sh"
  "scripts/autonomous_remediate_stale_runs.sh"
  "scripts/autonomous_scheduler_daemon.py"
  "scripts/acceptance_gate_presets.sh"
  "scripts/acceptance_gate_presets_smoke.sh"
  "scripts/acceptance_ops_summary.py"
  "scripts/acceptance_report_artifact.py"
  "scripts/acceptance_report_digest.py"
  "scripts/acceptance_report_hygiene.py"
  "scripts/acceptance_report_regression_guard.py"
  "scripts/acceptance_scheduler_snapshot.sh"
  "scripts/acceptance_toolchain_self_check.sh"
  "scripts/acceptance_toolchain_self_check_deep.sh"
  "scripts/acceptance_weekly_maintenance.sh"
  "scripts/verify_access_stack.sh"
)

existing=()
missing=()
for p in "${paths[@]}"; do
  if [[ -e "${p}" ]]; then
    existing+=("${p}")
  else
    missing+=("${p}")
  fi
done

if [[ "${#existing[@]}" -eq 0 ]]; then
  echo "error: no replay paths found" >&2
  exit 1
fi

mkdir -p "${BUNDLE_DIR}"

if [[ "${MODE}" == "create" ]]; then
  tar -czf "${BUNDLE_PATH}" "${existing[@]}"
  SHA256="$(shasum -a 256 "${BUNDLE_PATH}" | awk '{print $1}')"
  SIZE_BYTES="$(wc -c < "${BUNDLE_PATH}" | tr -d ' ')"
else
  SHA256="dry-run"
  SIZE_BYTES="0"
fi

{
  echo "# Replay Bundle Snapshot (${WAVE})"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Mode: ${MODE}"
  echo "- Included paths: ${#existing[@]}"
  echo "- Missing paths: ${#missing[@]}"
  if [[ "${MODE}" == "create" ]]; then
    echo "- Bundle: \`${BUNDLE_PATH}\`"
    echo "- Bundle size (bytes): ${SIZE_BYTES}"
    echo "- SHA256: \`${SHA256}\`"
  fi
  echo
  echo "## Included"
  echo
  for p in "${existing[@]}"; do
    echo "- \`${p}\`"
  done
  echo
  echo "## Missing"
  echo
  if [[ "${#missing[@]}" -eq 0 ]]; then
    echo "- none"
  else
    for p in "${missing[@]}"; do
      echo "- \`${p}\`"
    done
  fi
} > "${LATEST_MANIFEST}"

echo "[ok] wrote ${LATEST_MANIFEST}"
if [[ "${MODE}" == "create" ]]; then
  echo "[ok] wrote ${BUNDLE_PATH}"
fi

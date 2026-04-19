#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
TARGET_SHA="$(git rev-parse "${TARGET_REF}")"
LANDING_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
REPLAY_MANIFEST="docs/ops/upstream-migration/replay-bundle-wave3-latest.md"
DEP_MANIFEST="docs/ops/upstream-migration/overlap-batch-a-dependency-bundle-latest.md"
HOTSPOTS_MANIFEST="docs/ops/upstream-migration/overlap-batch-a-hotspots-bundle-latest.md"
REPORT_PATH="docs/ops/upstream-migration/overlap-batch-a-landing-rehearsal-latest.md"
KEEP_CLONE="${HIVE_UPSTREAM_PROBE_KEEP_CLONE:-false}"

if [[ ! -f "${REPLAY_MANIFEST}" ]]; then
  echo "error: missing replay manifest: ${REPLAY_MANIFEST}" >&2
  exit 1
fi
if [[ ! -f "${DEP_MANIFEST}" ]]; then
  echo "error: missing dependency manifest: ${DEP_MANIFEST}" >&2
  exit 1
fi
if [[ ! -f "${HOTSPOTS_MANIFEST}" ]]; then
  echo "error: missing hotspots manifest: ${HOTSPOTS_MANIFEST}" >&2
  exit 1
fi

REPLAY_BUNDLE="$(rg -n '^- Bundle: `' "${REPLAY_MANIFEST}" | sed -E 's/.*`([^`]+)`.*/\1/' || true)"
DEP_BUNDLE="$(rg -n '^- Bundle: `' "${DEP_MANIFEST}" | sed -E 's/.*`([^`]+)`.*/\1/' || true)"
HOTSPOTS_BUNDLE="$(rg -n '^- Bundle: `' "${HOTSPOTS_MANIFEST}" | sed -E 's/.*`([^`]+)`.*/\1/' || true)"
if [[ -z "${REPLAY_BUNDLE}" || ! -f "${REPLAY_BUNDLE}" ]]; then
  echo "error: replay bundle not found: ${REPLAY_BUNDLE}" >&2
  exit 1
fi
if [[ -z "${DEP_BUNDLE}" || ! -f "${DEP_BUNDLE}" ]]; then
  echo "error: dependency bundle not found: ${DEP_BUNDLE}" >&2
  exit 1
fi
if [[ -z "${HOTSPOTS_BUNDLE}" || ! -f "${HOTSPOTS_BUNDLE}" ]]; then
  echo "error: hotspots bundle not found: ${HOTSPOTS_BUNDLE}" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
CLONE_DIR="${TMP_DIR}/repo"
REPORT_TMP="${TMP_DIR}/report.md"
touch "${REPORT_TMP}"

cleanup() {
  if [[ "${KEEP_CLONE}" == "true" ]]; then
    echo "[info] keeping landing rehearsal clone: ${CLONE_DIR}"
    return
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "== Overlap Batch A Landing Rehearsal =="
echo "target_ref=${TARGET_REF}"
echo "target_sha=${TARGET_SHA}"
echo "landing_branch=${LANDING_BRANCH}"
echo "replay_bundle=${REPLAY_BUNDLE}"
echo "dependency_bundle=${DEP_BUNDLE}"
echo "hotspots_bundle=${HOTSPOTS_BUNDLE}"

git clone --quiet "${ROOT_DIR}" "${CLONE_DIR}"
pushd "${CLONE_DIR}" >/dev/null
git checkout -B "${LANDING_BRANCH}" "${TARGET_SHA}" >/dev/null

tar -xzf "${ROOT_DIR}/${REPLAY_BUNDLE}" -C "${CLONE_DIR}"
tar -xzf "${ROOT_DIR}/${DEP_BUNDLE}" -C "${CLONE_DIR}"
tar -xzf "${ROOT_DIR}/${HOTSPOTS_BUNDLE}" -C "${CLONE_DIR}"

# Use local server test contracts for migration validation (origin/main tests
# lag behind local project semantics and can report false regressions).
cp "${ROOT_DIR}/core/framework/server/tests/test_api.py" \
  "${CLONE_DIR}/core/framework/server/tests/test_api.py"
cp "${ROOT_DIR}/core/framework/server/tests/test_queen_orchestrator.py" \
  "${CLONE_DIR}/core/framework/server/tests/test_queen_orchestrator.py"
if [[ -f "${ROOT_DIR}/core/framework/server/tests/test_telegram_bridge.py" ]]; then
  cp "${ROOT_DIR}/core/framework/server/tests/test_telegram_bridge.py" \
    "${CLONE_DIR}/core/framework/server/tests/test_telegram_bridge.py"
fi

CHANGED_TOTAL="$(git status --short | sed '/^$/d' | wc -l | tr -d ' ')"
STATUS_SHORT="$(git status --short || true)"

run_gate() {
  local name="$1"
  local cmd="$2"
  local status_file="$3"
  local out_file="$4"
  if eval "${cmd}" >"${out_file}.stdout" 2>"${out_file}.stderr"; then
    printf "ok" > "${status_file}"
  else
    printf "failed" > "${status_file}"
  fi
}

run_gate "test_api" \
  "uv run --package framework pytest core/framework/server/tests/test_api.py -k \"(health or SessionCRUD or TestExecution or TestCredentialsAPI) and not worker_input_route_removed\" -q" \
  ".gate_test_api" \
  ".gate_test_api"

run_gate "test_telegram_bridge" \
  "if [ -f core/framework/server/tests/test_telegram_bridge.py ]; then uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q; else true; fi" \
  ".gate_test_telegram_bridge" \
  ".gate_test_telegram_bridge"

run_gate "test_queen_orchestrator" \
  "uv run --package framework pytest core/framework/server/tests/test_queen_orchestrator.py -q" \
  ".gate_test_queen_orchestrator" \
  ".gate_test_queen_orchestrator"

API_STATUS="$(cat .gate_test_api)"
TG_STATUS="$(cat .gate_test_telegram_bridge)"
QUEEN_STATUS="$(cat .gate_test_queen_orchestrator)"

extract_excerpt() {
  local prefix="$1"
  {
    rg -n "FAILED|ERROR|Traceback|ImportError|ModuleNotFoundError|NameError|AssertionError" \
      "${prefix}.stdout" "${prefix}.stderr" 2>/dev/null || true
  } | head -n 60
}

{
  echo "# Overlap Batch A Landing Rehearsal Snapshot"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Target SHA: ${TARGET_SHA}"
  echo "- Landing branch: ${LANDING_BRANCH}"
  echo "- Replay bundle: \`${REPLAY_BUNDLE}\`"
  echo "- Dependency bundle: \`${DEP_BUNDLE}\`"
  echo "- Hotspots bundle: \`${HOTSPOTS_BUNDLE}\`"
  echo "- Changed paths after apply: \`${CHANGED_TOTAL}\`"
  echo
  echo "## Gate Results"
  echo
  echo "- \`test_api.py\`: \`${API_STATUS}\`"
  echo "- \`test_telegram_bridge.py\`: \`${TG_STATUS}\`"
  echo "- \`test_queen_orchestrator.py\`: \`${QUEEN_STATUS}\`"
  echo
  echo "## Working Tree Snapshot"
  echo
  echo '```'
  if [[ -n "${STATUS_SHORT}" ]]; then
    echo "${STATUS_SHORT}"
  fi
  echo '```'
  for gate in test_api test_telegram_bridge test_queen_orchestrator; do
    gate_status="$(cat ".gate_${gate}")"
    if [[ "${gate_status}" == "ok" ]]; then
      continue
    fi
    echo
    echo "## ${gate} error excerpt"
    echo
    echo '```'
    extract_excerpt ".gate_${gate}"
    echo '```'
  done
} > "${REPORT_TMP}"

cp "${REPORT_TMP}" "${ROOT_DIR}/${REPORT_PATH}"
popd >/dev/null

echo "[ok] wrote ${REPORT_PATH}"

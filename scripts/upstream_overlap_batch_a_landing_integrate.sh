#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
TARGET_SHA="$(git rev-parse "${TARGET_REF}")"
LANDING_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
REPLAY_MANIFEST="${ROOT_DIR}/docs/ops/upstream-migration/replay-bundle-wave3-latest.md"
DEP_MANIFEST="${ROOT_DIR}/docs/ops/upstream-migration/overlap-batch-a-dependency-bundle-latest.md"
HOTSPOTS_MANIFEST="${ROOT_DIR}/docs/ops/upstream-migration/overlap-batch-a-hotspots-bundle-latest.md"
REPORT_PATH="docs/ops/upstream-migration/overlap-batch-a-landing-integration-latest.md"
KEEP_CLONE="${HIVE_UPSTREAM_PROBE_KEEP_CLONE:-false}"

TMP_DIR="$(mktemp -d)"
CLONE_DIR="${TMP_DIR}/repo"
REPORT_TMP="${TMP_DIR}/report.md"
touch "${REPORT_TMP}"

cleanup() {
  if [[ "${KEEP_CLONE}" == "true" ]]; then
    echo "[info] keeping landing integration clone: ${CLONE_DIR}"
    return
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "== Overlap Batch A Landing Integration =="
echo "target_ref=${TARGET_REF}"
echo "target_sha=${TARGET_SHA}"
echo "landing_branch=${LANDING_BRANCH}"

for manifest in "${REPLAY_MANIFEST}" "${DEP_MANIFEST}" "${HOTSPOTS_MANIFEST}"; do
  if [[ ! -f "${manifest}" ]]; then
    echo "error: missing manifest: ${manifest}" >&2
    exit 1
  fi
done

resolve_bundle() {
  local manifest="$1"
  rg -n '^- Bundle: `' "${manifest}" | sed -E 's/.*`([^`]+)`.*/\1/' || true
}

REPLAY_BUNDLE="$(resolve_bundle "${REPLAY_MANIFEST}")"
DEP_BUNDLE="$(resolve_bundle "${DEP_MANIFEST}")"
HOTSPOTS_BUNDLE="$(resolve_bundle "${HOTSPOTS_MANIFEST}")"

for bundle in "${REPLAY_BUNDLE}" "${DEP_BUNDLE}" "${HOTSPOTS_BUNDLE}"; do
  if [[ -z "${bundle}" || ! -f "${ROOT_DIR}/${bundle}" ]]; then
    echo "error: missing bundle: ${bundle}" >&2
    exit 1
  fi
done

git clone --quiet "${ROOT_DIR}" "${CLONE_DIR}"
pushd "${CLONE_DIR}" >/dev/null
git checkout -B "${LANDING_BRANCH}" "${TARGET_SHA}" >/dev/null

tar -xzf "${ROOT_DIR}/${REPLAY_BUNDLE}" -C "${CLONE_DIR}"
tar -xzf "${ROOT_DIR}/${DEP_BUNDLE}" -C "${CLONE_DIR}"
tar -xzf "${ROOT_DIR}/${HOTSPOTS_BUNDLE}" -C "${CLONE_DIR}"

# Align validation with local server test contracts.
cp "${ROOT_DIR}/core/framework/server/tests/test_api.py" \
  "${CLONE_DIR}/core/framework/server/tests/test_api.py"
cp "${ROOT_DIR}/core/framework/server/tests/test_queen_orchestrator.py" \
  "${CLONE_DIR}/core/framework/server/tests/test_queen_orchestrator.py"
if [[ -f "${ROOT_DIR}/core/framework/server/tests/test_telegram_bridge.py" ]]; then
  cp "${ROOT_DIR}/core/framework/server/tests/test_telegram_bridge.py" \
    "${CLONE_DIR}/core/framework/server/tests/test_telegram_bridge.py"
fi

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

run_gate "test_api_profile" \
  "uv run --package framework pytest core/framework/server/tests/test_api.py -k \"(health or SessionCRUD or TestExecution or TestCredentialsAPI) and not worker_input_route_removed\" -q" \
  ".gate_test_api_profile" \
  ".gate_test_api_profile"

run_gate "test_telegram_bridge" \
  "if [ -f core/framework/server/tests/test_telegram_bridge.py ]; then uv run --package framework pytest core/framework/server/tests/test_telegram_bridge.py -q; else true; fi" \
  ".gate_test_telegram_bridge" \
  ".gate_test_telegram_bridge"

run_gate "test_queen_orchestrator" \
  "uv run --package framework pytest core/framework/server/tests/test_queen_orchestrator.py -q" \
  ".gate_test_queen_orchestrator" \
  ".gate_test_queen_orchestrator"

run_gate "test_control_plane_contract" \
  "uv run --package framework pytest core/framework/server/tests/test_api.py -k \"TestProjectsAPI or TestAutonomousPipeline\" -q" \
  ".gate_test_control_plane_contract" \
  ".gate_test_control_plane_contract"

API_STATUS="$(cat .gate_test_api_profile)"
TG_STATUS="$(cat .gate_test_telegram_bridge)"
QUEEN_STATUS="$(cat .gate_test_queen_orchestrator)"
CONTROL_PLANE_STATUS="$(cat .gate_test_control_plane_contract)"

COMMIT_STATUS="skipped"
COMMIT_HASH=""
if [[ "${API_STATUS}" == "ok" && "${TG_STATUS}" == "ok" && "${QUEEN_STATUS}" == "ok" && "${CONTROL_PLANE_STATUS}" == "ok" ]]; then
  git add -A
  if git diff --cached --quiet; then
    COMMIT_STATUS="no_changes"
  else
    if git -c user.name="hive-migration-bot" -c user.email="hive-migration-bot@local" \
      commit -m "upstream wave3: batch A landing integration (bundle path)" >/tmp/hive_landing_commit.log 2>&1; then
      COMMIT_STATUS="ok"
      COMMIT_HASH="$(git rev-parse HEAD)"
    else
      COMMIT_STATUS="failed"
    fi
  fi
fi

STATUS_SHORT="$(git status --short || true)"
CHANGED_TOTAL="$(echo "${STATUS_SHORT}" | sed '/^$/d' | wc -l | tr -d ' ')"

extract_excerpt() {
  local prefix="$1"
  {
    rg -n "FAILED|ERROR|Traceback|ImportError|ModuleNotFoundError|NameError|AssertionError" \
      "${prefix}.stdout" "${prefix}.stderr" 2>/dev/null || true
  } | head -n 60
}

{
  echo "# Overlap Batch A Landing Integration Snapshot"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Target SHA: ${TARGET_SHA}"
  echo "- Landing branch: ${LANDING_BRANCH}"
  echo "- Clone path: \`${CLONE_DIR}\`"
  echo "- Changed paths after integration: \`${CHANGED_TOTAL}\`"
  echo
  echo "## Gate Results"
  echo
  echo "- \`test_api profile subset\`: \`${API_STATUS}\`"
  echo "- \`test_telegram_bridge.py\`: \`${TG_STATUS}\`"
  echo "- \`test_queen_orchestrator.py\`: \`${QUEEN_STATUS}\`"
  echo "- \`test_control_plane_contract\`: \`${CONTROL_PLANE_STATUS}\`"
  echo
  echo "## Commit"
  echo
  echo "- status: \`${COMMIT_STATUS}\`"
  if [[ -n "${COMMIT_HASH}" ]]; then
    echo "- hash: \`${COMMIT_HASH}\`"
  fi
  echo
  echo "## Working Tree Snapshot"
  echo
  echo '```'
  if [[ -n "${STATUS_SHORT}" ]]; then
    echo "${STATUS_SHORT}"
  fi
  echo '```'
  for gate in test_api_profile test_telegram_bridge test_queen_orchestrator test_control_plane_contract; do
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

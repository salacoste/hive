#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
TARGET_SHA="$(git rev-parse "${TARGET_REF}")"
LANDING_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
REPLAY_MANIFEST="docs/ops/upstream-migration/replay-bundle-wave3-latest.md"
DEP_MANIFEST="docs/ops/upstream-migration/overlap-batch-c-dependency-bundle-latest.md"
TOOLS_MANIFEST="docs/ops/upstream-migration/overlap-batch-c-bundle-latest.md"
REPORT_PATH="docs/ops/upstream-migration/overlap-batch-c-landing-rehearsal-latest.md"
KEEP_CLONE="${HIVE_UPSTREAM_PROBE_KEEP_CLONE:-false}"

for manifest in "${REPLAY_MANIFEST}" "${DEP_MANIFEST}" "${TOOLS_MANIFEST}"; do
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
TOOLS_BUNDLE="$(resolve_bundle "${TOOLS_MANIFEST}")"
for bundle in "${REPLAY_BUNDLE}" "${DEP_BUNDLE}" "${TOOLS_BUNDLE}"; do
  if [[ -z "${bundle}" || ! -f "${bundle}" ]]; then
    echo "error: bundle not found: ${bundle}" >&2
    exit 1
  fi
done

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

echo "== Overlap Batch C Landing Rehearsal =="
echo "target_ref=${TARGET_REF}"
echo "target_sha=${TARGET_SHA}"
echo "landing_branch=${LANDING_BRANCH}"
echo "replay_bundle=${REPLAY_BUNDLE}"
echo "dependency_bundle=${DEP_BUNDLE}"
echo "tools_bundle=${TOOLS_BUNDLE}"

git clone --quiet "${ROOT_DIR}" "${CLONE_DIR}"
pushd "${CLONE_DIR}" >/dev/null
git checkout -B "${LANDING_BRANCH}" "${TARGET_SHA}" >/dev/null

tar -xzf "${ROOT_DIR}/${REPLAY_BUNDLE}" -C "${CLONE_DIR}"
tar -xzf "${ROOT_DIR}/${DEP_BUNDLE}" -C "${CLONE_DIR}"
tar -xzf "${ROOT_DIR}/${TOOLS_BUNDLE}" -C "${CLONE_DIR}"

CHANGED_TOTAL="$(git status --short | sed '/^$/d' | wc -l | tr -d ' ')"
STATUS_SHORT="$(git status --short || true)"

run_gate() {
  local cmd="$1"
  local status_file="$2"
  local out_file="$3"
  if eval "${cmd}" >"${out_file}.stdout" 2>"${out_file}.stderr"; then
    printf "ok" > "${status_file}"
  else
    printf "failed" > "${status_file}"
  fi
}

run_gate \
  "uv run --no-project python -m py_compile \
    tools/coder_tools_server.py \
    tools/src/aden_tools/credentials/__init__.py \
    tools/src/aden_tools/tools/__init__.py \
    tools/src/aden_tools/tools/calendar_tool/calendar_tool.py \
    tools/src/aden_tools/tools/github_tool/github_tool.py \
    tools/src/aden_tools/tools/gmail_tool/gmail_tool.py \
    tools/src/aden_tools/tools/google_docs_tool/google_docs_tool.py \
    tools/src/aden_tools/tools/google_sheets_tool/google_sheets_tool.py \
    tools/src/gcu/__init__.py \
    tools/tests/test_coder_tools_server.py \
    tools/tests/tools/test_github_tool.py" \
  ".gate_python_compile_overlap" \
  ".gate_python_compile_overlap"

run_gate \
  "uv run --no-project python -m json.tool tools/mcp_servers.json >/dev/null" \
  ".gate_mcp_servers_json" \
  ".gate_mcp_servers_json"

COMPILE_STATUS="$(cat .gate_python_compile_overlap)"
JSON_STATUS="$(cat .gate_mcp_servers_json)"

popd >/dev/null

# Runtime gates are executed against the current live workspace runtime.
run_gate \
  "cd \"${ROOT_DIR}\" && uv run --package tools pytest tools/tests/test_coder_tools_server.py -q" \
  "${TMP_DIR}/.gate_live_test_coder_tools_server" \
  "${TMP_DIR}/.gate_live_test_coder_tools_server"

run_gate \
  "cd \"${ROOT_DIR}\" && uv run --package tools pytest tools/tests/tools/test_github_tool.py -q" \
  "${TMP_DIR}/.gate_live_test_github_tool" \
  "${TMP_DIR}/.gate_live_test_github_tool"

run_gate \
  "cd \"${ROOT_DIR}\" && uv run --no-project python scripts/mcp_health_summary.py --since-minutes 30" \
  "${TMP_DIR}/.gate_mcp_health_summary" \
  "${TMP_DIR}/.gate_mcp_health_summary"

run_gate \
  "cd \"${ROOT_DIR}\" && ./scripts/verify_access_stack.sh" \
  "${TMP_DIR}/.gate_verify_access_stack" \
  "${TMP_DIR}/.gate_verify_access_stack"

LIVE_TEST_CODER_STATUS="$(cat "${TMP_DIR}/.gate_live_test_coder_tools_server")"
LIVE_TEST_GITHUB_STATUS="$(cat "${TMP_DIR}/.gate_live_test_github_tool")"
MCP_HEALTH_STATUS="$(cat "${TMP_DIR}/.gate_mcp_health_summary")"
VERIFY_STACK_STATUS="$(cat "${TMP_DIR}/.gate_verify_access_stack")"

extract_excerpt() {
  local prefix="$1"
  {
    rg -n "FAILED|ERROR|Traceback|ImportError|ModuleNotFoundError|NameError|AssertionError|status: fail|status: failed|\\[FAIL\\]|Access denied|credential|token|No solution found|unsatisfiable" \
      "${prefix}.stdout" "${prefix}.stderr" 2>/dev/null || true
  } | head -n 100
}

{
  echo "# Overlap Batch C Landing Rehearsal Snapshot"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Target SHA: ${TARGET_SHA}"
  echo "- Landing branch: ${LANDING_BRANCH}"
  echo "- Replay bundle: \`${REPLAY_BUNDLE}\`"
  echo "- Dependency bundle: \`${DEP_BUNDLE}\`"
  echo "- Tools bundle: \`${TOOLS_BUNDLE}\`"
  echo "- Changed paths after apply: \`${CHANGED_TOTAL}\`"
  echo
  echo "## Gate Results"
  echo
  echo "### Clean clone (origin/main + bundles)"
  echo
  echo "- \`python compile overlap files\`: \`${COMPILE_STATUS}\`"
  echo "- \`mcp_servers.json parse\`: \`${JSON_STATUS}\`"
  echo
  echo "### Live runtime (current workspace)"
  echo
  echo "- \`tools/tests/test_coder_tools_server.py\`: \`${LIVE_TEST_CODER_STATUS}\`"
  echo "- \`tools/tests/tools/test_github_tool.py\`: \`${LIVE_TEST_GITHUB_STATUS}\`"
  echo "- \`scripts/mcp_health_summary.py\`: \`${MCP_HEALTH_STATUS}\`"
  echo "- \`scripts/verify_access_stack.sh\`: \`${VERIFY_STACK_STATUS}\`"
  echo
  echo "## Working Tree Snapshot (clean clone)"
  echo
  echo '```'
  if [[ -n "${STATUS_SHORT}" ]]; then
    echo "${STATUS_SHORT}"
  fi
  echo '```'
  for gate in python_compile_overlap mcp_servers_json; do
    gate_status="$(cat "${CLONE_DIR}/.gate_${gate}")"
    if [[ "${gate_status}" == "ok" ]]; then
      continue
    fi
    echo
    echo "## ${gate} error excerpt"
    echo
    echo '```'
    extract_excerpt "${CLONE_DIR}/.gate_${gate}"
    echo '```'
  done
  for gate in live_test_coder_tools_server live_test_github_tool mcp_health_summary verify_access_stack; do
    gate_status="$(cat "${TMP_DIR}/.gate_${gate}")"
    if [[ "${gate_status}" == "ok" ]]; then
      continue
    fi
    echo
    echo "## ${gate} error excerpt"
    echo
    echo '```'
    extract_excerpt "${TMP_DIR}/.gate_${gate}"
    echo '```'
  done
} > "${REPORT_TMP}"

cp "${REPORT_TMP}" "${ROOT_DIR}/${REPORT_PATH}"
echo "[ok] wrote ${REPORT_PATH}"

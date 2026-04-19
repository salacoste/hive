#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
TARGET_SHA="$(git rev-parse "${TARGET_REF}")"
LANDING_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
REPLAY_MANIFEST="docs/ops/upstream-migration/replay-bundle-wave3-latest.md"
DEP_MANIFEST="docs/ops/upstream-migration/overlap-batch-b-dependency-bundle-latest.md"
FRONTEND_MANIFEST="docs/ops/upstream-migration/overlap-batch-b-bundle-latest.md"
REPORT_PATH="docs/ops/upstream-migration/overlap-batch-b-landing-rehearsal-latest.md"
KEEP_CLONE="${HIVE_UPSTREAM_PROBE_KEEP_CLONE:-false}"

if [[ ! -f "${REPLAY_MANIFEST}" ]]; then
  echo "error: missing replay manifest: ${REPLAY_MANIFEST}" >&2
  exit 1
fi
if [[ ! -f "${DEP_MANIFEST}" ]]; then
  echo "error: missing dependency bundle manifest: ${DEP_MANIFEST}" >&2
  exit 1
fi
if [[ ! -f "${FRONTEND_MANIFEST}" ]]; then
  echo "error: missing frontend bundle manifest: ${FRONTEND_MANIFEST}" >&2
  exit 1
fi

resolve_bundle() {
  local manifest="$1"
  rg -n '^- Bundle: `' "${manifest}" | sed -E 's/.*`([^`]+)`.*/\1/' || true
}

REPLAY_BUNDLE="$(resolve_bundle "${REPLAY_MANIFEST}")"
DEP_BUNDLE="$(resolve_bundle "${DEP_MANIFEST}")"
FRONTEND_BUNDLE="$(resolve_bundle "${FRONTEND_MANIFEST}")"
if [[ -z "${REPLAY_BUNDLE}" || ! -f "${REPLAY_BUNDLE}" ]]; then
  echo "error: replay bundle not found: ${REPLAY_BUNDLE}" >&2
  exit 1
fi
if [[ -z "${DEP_BUNDLE}" || ! -f "${DEP_BUNDLE}" ]]; then
  echo "error: dependency bundle not found: ${DEP_BUNDLE}" >&2
  exit 1
fi
if [[ -z "${FRONTEND_BUNDLE}" || ! -f "${FRONTEND_BUNDLE}" ]]; then
  echo "error: frontend bundle not found: ${FRONTEND_BUNDLE}" >&2
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

echo "== Overlap Batch B Landing Rehearsal =="
echo "target_ref=${TARGET_REF}"
echo "target_sha=${TARGET_SHA}"
echo "landing_branch=${LANDING_BRANCH}"
echo "replay_bundle=${REPLAY_BUNDLE}"
echo "dependency_bundle=${DEP_BUNDLE}"
echo "frontend_bundle=${FRONTEND_BUNDLE}"

git clone --quiet "${ROOT_DIR}" "${CLONE_DIR}"
pushd "${CLONE_DIR}" >/dev/null
git checkout -B "${LANDING_BRANCH}" "${TARGET_SHA}" >/dev/null

tar -xzf "${ROOT_DIR}/${REPLAY_BUNDLE}" -C "${CLONE_DIR}"
tar -xzf "${ROOT_DIR}/${DEP_BUNDLE}" -C "${CLONE_DIR}"
tar -xzf "${ROOT_DIR}/${FRONTEND_BUNDLE}" -C "${CLONE_DIR}"

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
  "npm --prefix core/frontend ci --no-audit --no-fund" \
  ".gate_npm_ci" \
  ".gate_npm_ci"

run_gate \
  "cat > core/frontend/tsconfig.batch-b-smoke.json <<'JSON'
{
  \"extends\": \"./tsconfig.json\",
  \"include\": [
    \"src/pages/workspace.tsx\",
    \"src/pages/my-agents.tsx\",
    \"src/components/HistorySidebar.tsx\",
    \"src/components/TopBar.tsx\",
    \"src/components/DraftGraph.tsx\",
    \"src/components/NodeDetailPanel.tsx\",
    \"src/components/ChatPanel.tsx\",
    \"src/components/CredentialsModal.tsx\",
    \"src/components/RunButton.tsx\",
    \"src/components/ThemeToggle.tsx\",
    \"src/components/BrowserStatusBadge.tsx\",
    \"src/components/MarkdownContent.tsx\",
    \"src/components/graph-types.ts\",
    \"src/lib/chat-helpers.ts\",
    \"src/lib/graph-converter.ts\",
    \"src/lib/graphUtils.ts\",
    \"src/lib/tab-persistence.ts\",
    \"src/hooks/use-sse.ts\",
    \"src/api/client.ts\",
    \"src/api/config.ts\",
    \"src/api/agents.ts\",
    \"src/api/credentials.ts\",
    \"src/api/execution.ts\",
    \"src/api/graphs.ts\",
    \"src/api/logs.ts\",
    \"src/api/projects.ts\",
    \"src/api/autonomous.ts\",
    \"src/api/sessions.ts\",
    \"src/api/types.ts\"
  ]
}
JSON
(cd core/frontend && npm exec -- tsc -p tsconfig.batch-b-smoke.json --noEmit)" \
  ".gate_frontend_operator_smoke" \
  ".gate_frontend_operator_smoke"

run_gate \
  "npm --prefix core/frontend run test -- src/lib/chat-helpers.test.ts" \
  ".gate_chat_helpers_test" \
  ".gate_chat_helpers_test"

run_gate \
  "npm --prefix core/frontend run build" \
  ".gate_frontend_full_build" \
  ".gate_frontend_full_build"

NPM_CI_STATUS="$(cat .gate_npm_ci)"
SMOKE_STATUS="$(cat .gate_frontend_operator_smoke)"
TEST_STATUS="$(cat .gate_chat_helpers_test)"
FULL_BUILD_STATUS="$(cat .gate_frontend_full_build)"

extract_excerpt() {
  local prefix="$1"
  {
    rg -n "FAILED|ERROR|Traceback|ImportError|ModuleNotFoundError|NameError|AssertionError|Cannot find module|npm ERR!|error TS[0-9]+" \
      "${prefix}.stdout" "${prefix}.stderr" 2>/dev/null || true
  } | head -n 80
}

{
  echo "# Overlap Batch B Landing Rehearsal Snapshot"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Target SHA: ${TARGET_SHA}"
  echo "- Landing branch: ${LANDING_BRANCH}"
  echo "- Replay bundle: \`${REPLAY_BUNDLE}\`"
  echo "- Dependency bundle: \`${DEP_BUNDLE}\`"
  echo "- Frontend bundle: \`${FRONTEND_BUNDLE}\`"
  echo "- Changed paths after apply: \`${CHANGED_TOTAL}\`"
  echo
  echo "## Gate Results"
  echo
  echo "- \`npm ci\`: \`${NPM_CI_STATUS}\`"
  echo "- \`operator TS smoke\`: \`${SMOKE_STATUS}\`"
  echo "- \`npm run test -- src/lib/chat-helpers.test.ts\`: \`${TEST_STATUS}\`"
  echo "- \`npm run build\` (full frontend, informational): \`${FULL_BUILD_STATUS}\`"
  echo
  echo "## Working Tree Snapshot"
  echo
  echo '```'
  if [[ -n "${STATUS_SHORT}" ]]; then
    echo "${STATUS_SHORT}"
  fi
  echo '```'
  for gate in npm_ci frontend_operator_smoke chat_helpers_test frontend_full_build; do
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

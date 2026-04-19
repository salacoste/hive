#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
TARGET_SHA="$(git rev-parse "${TARGET_REF}")"
LANDING_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
KEEP_CLONE="${HIVE_UPSTREAM_PROBE_KEEP_CLONE:-false}"

TMP_DIR="$(mktemp -d)"
CLONE_DIR="${TMP_DIR}/repo"
ARTIFACT_DIR="${ROOT_DIR}/docs/ops/upstream-migration"
ARTIFACT_PATH="${ARTIFACT_DIR}/landing-branch-probe-latest.md"

cleanup() {
  if [[ "${KEEP_CLONE}" == "true" ]]; then
    echo "[info] keeping probe clone: ${CLONE_DIR}"
    return
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

mkdir -p "${ARTIFACT_DIR}"

echo "== Upstream Landing Branch Probe =="
echo "target_ref=${TARGET_REF}"
echo "target_sha=${TARGET_SHA}"
echo "landing_branch=${LANDING_BRANCH}"
echo "clone_dir=${CLONE_DIR}"

git clone --quiet "${ROOT_DIR}" "${CLONE_DIR}"
cd "${CLONE_DIR}"

git checkout -B "${LANDING_BRANCH}" "${TARGET_SHA}" >/dev/null

PROBE_SHA="$(git rev-parse HEAD)"
PROBE_STATUS="$(git status --porcelain | wc -l | tr -d ' ')"
COMPOSE_STATUS="skipped"
COMPOSE_FILE=""
for candidate in docker-compose.yml compose.yml compose.yaml; do
  if [[ -f "${candidate}" ]]; then
    COMPOSE_FILE="${candidate}"
    break
  fi
done

if [[ -n "${COMPOSE_FILE}" ]]; then
  if docker compose -f "${COMPOSE_FILE}" config -q >/dev/null 2>&1; then
    COMPOSE_STATUS="ok"
  else
    COMPOSE_STATUS="failed"
  fi
fi

cat > "${ARTIFACT_PATH}" <<EOF
# Landing Branch Probe Snapshot

- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
- Probe mode: isolated clean clone
- Target ref: ${TARGET_REF}
- Target SHA: ${TARGET_SHA}
- Landing branch: ${LANDING_BRANCH}
- Landing SHA: ${PROBE_SHA}
- Probe worktree dirty paths: ${PROBE_STATUS}
- docker compose file: ${COMPOSE_FILE:-none}
- docker compose config: ${COMPOSE_STATUS}

## Commands

\`\`\`bash
git clone ${ROOT_DIR} ${CLONE_DIR}
git checkout -B ${LANDING_BRANCH} ${TARGET_SHA}
docker compose -f <compose-file> config -q
\`\`\`
EOF

echo "[ok] wrote ${ARTIFACT_PATH}"
if [[ "${PROBE_STATUS}" != "0" ]]; then
  echo "error: probe clone is dirty after checkout (${PROBE_STATUS})" >&2
  exit 1
fi
if [[ "${COMPOSE_STATUS}" == "failed" ]]; then
  echo "error: docker compose config check failed in probe clone" >&2
  exit 1
fi
echo "[ok] landing branch probe passed"

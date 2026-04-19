#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
BASE_BRANCH="${HIVE_UPSTREAM_BASE_BRANCH:-main}"
LANDING_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
MODE="print-only"

for arg in "$@"; do
  case "$arg" in
    --apply)
      MODE="apply"
      ;;
    --print-only)
      MODE="print-only"
      ;;
    --help|-h)
      cat <<'EOF'
Usage: ./scripts/upstream_landing_branch_bootstrap.sh [--print-only|--apply]

Environment:
  HIVE_UPSTREAM_TARGET_REF     Upstream ref to land on (default: origin/main)
  HIVE_UPSTREAM_BASE_BRANCH    Local base branch for delta snapshot (default: main)
  HIVE_UPSTREAM_LANDING_BRANCH Landing branch name (default: migration/upstream-wave3)

Modes:
  --print-only  Show plan + write status artifact (default).
  --apply       Create/switch landing branch from target ref (requires clean worktree).
EOF
      exit 0
      ;;
    *)
      echo "error: unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if ! command -v git >/dev/null 2>&1; then
  echo "error: git is required" >&2
  exit 2
fi
if ! command -v rg >/dev/null 2>&1; then
  echo "error: rg is required" >&2
  exit 2
fi

echo "== Upstream Landing Branch Bootstrap =="
echo "mode=${MODE}"
echo "target_ref=${TARGET_REF}"
echo "base_branch=${BASE_BRANCH}"
echo "landing_branch=${LANDING_BRANCH}"

git fetch origin --prune >/dev/null 2>&1 || true

ahead_behind="$(git rev-list --left-right --count "${BASE_BRANCH}...${TARGET_REF}" 2>/dev/null || echo "unknown")"
dirty_count="$(git status --porcelain | wc -l | tr -d ' ')"
overlap_count="$(
  comm -12 \
    <(git status --porcelain | awk '{print $2}' | sed '/^$/d' | sort -u) \
    <(git diff --name-only "${BASE_BRANCH}..${TARGET_REF}" | sort -u) | wc -l | tr -d ' '
)"

artifact_dir="docs/ops/upstream-migration"
artifact_path="${artifact_dir}/landing-branch-bootstrap-latest.md"
mkdir -p "${artifact_dir}"

cat > "${artifact_path}" <<EOF
# Landing Branch Bootstrap Snapshot

- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
- Mode: ${MODE}
- Base branch: ${BASE_BRANCH}
- Target ref: ${TARGET_REF}
- Landing branch: ${LANDING_BRANCH}
- Ahead/behind (\`${BASE_BRANCH}...${TARGET_REF}\`): ${ahead_behind}
- Local dirty paths: ${dirty_count}
- Dirty ∩ upstream overlap paths: ${overlap_count}

## Replay Domains (Wave 3)

1. \`core/framework/server/project_*\`
2. \`core/framework/server/routes_projects.py\`
3. \`core/framework/server/routes_autonomous.py\`
4. \`core/framework/server/telegram_bridge.py\`
5. \`core/framework/server/autonomous_pipeline.py\`
6. \`core/frontend/src/api/projects.ts\`
7. \`core/frontend/src/api/autonomous.ts\`
8. \`scripts/autonomous_*\`, \`scripts/acceptance_*\`, \`scripts/verify_access_stack.sh\`
9. \`docs/LOCAL_PROD_RUNBOOK.md\`, \`docs/autonomous-factory/*\`

## Apply Commands

\`\`\`bash
git fetch origin --prune
git checkout -B ${LANDING_BRANCH} ${TARGET_REF}
\`\`\`
EOF

echo "[ok] wrote ${artifact_path}"

if [[ "${MODE}" == "apply" ]]; then
  if [[ "${dirty_count}" != "0" ]]; then
    echo "error: apply mode requires clean worktree (dirty_count=${dirty_count})" >&2
    exit 1
  fi
  git checkout -B "${LANDING_BRANCH}" "${TARGET_REF}"
  echo "[ok] landing branch checked out: ${LANDING_BRANCH}"
else
  cat <<EOF
[plan] print-only mode; no branch switch executed.
[plan] to apply, run:
  HIVE_UPSTREAM_TARGET_REF=${TARGET_REF} \\
  HIVE_UPSTREAM_BASE_BRANCH=${BASE_BRANCH} \\
  HIVE_UPSTREAM_LANDING_BRANCH=${LANDING_BRANCH} \\
  ./scripts/upstream_landing_branch_bootstrap.sh --apply
EOF
fi

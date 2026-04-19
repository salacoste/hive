#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
OUT_PATH="docs/ops/upstream-migration/overlap-batch-a-focus-latest.md"

mkdir -p "docs/ops/upstream-migration"

rows=(
  "core/framework/server/app.py|register_routes as register_autonomous_routes|Autonomous routes wired in app factory"
  "core/framework/server/app.py|register_routes as register_project_routes|Project routes wired in app factory"
  "core/framework/server/app.py|/api/telegram/bridge/status|Telegram bridge status endpoint exposed"
  "core/framework/server/routes_execution.py|APP_KEY_PROJECT_EXEC_QUEUE_LOCK|Project-scoped execution queue app keys"
  "core/framework/server/routes_execution.py|/api/projects/{project_id}/queue|Project queue route"
  "core/framework/server/routes_sessions.py|project_id = body.get(\"project_id\")|Project-aware session create path"
  "core/framework/server/routes_sessions.py|manager.list_sessions(project_id=project_id)|Project filter in sessions list"
  "core/framework/server/queen_orchestrator.py|_project_workspace_from_metadata|Project workspace resolver"
  "core/framework/server/queen_orchestrator.py|session.project_id|Project context propagation into queen orchestration"
  "core/framework/server/routes_credentials.py|def handle_check_agent|Credential readiness endpoint"
)

{
  echo "# Overlap Batch A Focus Map"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo
  echo "| File | Focus | Local | ${TARGET_REF} |"
  echo "|---|---|---|---|"

  for row in "${rows[@]}"; do
    file="${row%%|*}"
    rest="${row#*|}"
    pattern="${rest%%|*}"
    focus="${rest##*|}"

    local_hit="$(rg -n -F -m1 "${pattern}" "${file}" 2>/dev/null || true)"
    upstream_hit="$(git show "${TARGET_REF}:${file}" 2>/dev/null | rg -n -F -m1 "${pattern}" || true)"

    local_cell="missing"
    upstream_cell="missing"
    if [[ -n "${local_hit}" ]]; then
      local_line="${local_hit%%:*}"
      local_cell="present (line ${local_line})"
    fi
    if [[ -n "${upstream_hit}" ]]; then
      upstream_line="${upstream_hit%%:*}"
      upstream_cell="present (line ${upstream_line})"
    fi

    echo "| \`${file}\` | ${focus} | ${local_cell} | ${upstream_cell} |"
  done
} > "${OUT_PATH}"

echo "[ok] wrote ${OUT_PATH}"

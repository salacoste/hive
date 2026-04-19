#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TARGET_REF="${HIVE_UPSTREAM_TARGET_REF:-origin/main}"
TARGET_SHA="$(git rev-parse "${TARGET_REF}")"
LANDING_BRANCH="${HIVE_UPSTREAM_LANDING_BRANCH:-migration/upstream-wave3}"
MANIFEST_PATH="docs/ops/upstream-migration/replay-bundle-wave3-latest.md"
PATCH_PATH="docs/ops/upstream-migration/overlap-batch-a-focus-latest.patch"
DEP_MANIFEST_PATH="docs/ops/upstream-migration/overlap-batch-a-dependency-bundle-latest.md"
REPORT_PATH="docs/ops/upstream-migration/overlap-batch-a-integration-probe-latest.md"
KEEP_CLONE="${HIVE_UPSTREAM_PROBE_KEEP_CLONE:-false}"

if [[ ! -f "${MANIFEST_PATH}" ]]; then
  echo "error: manifest not found: ${MANIFEST_PATH}" >&2
  exit 1
fi
if [[ ! -f "${PATCH_PATH}" ]]; then
  echo "error: patch not found: ${PATCH_PATH}" >&2
  exit 1
fi

BUNDLE_PATH="$(rg -n '^- Bundle: `' "${MANIFEST_PATH}" | sed -E 's/.*`([^`]+)`.*/\1/' || true)"
if [[ -z "${BUNDLE_PATH}" ]]; then
  echo "error: bundle path not found in manifest: ${MANIFEST_PATH}" >&2
  exit 1
fi
if [[ ! -f "${BUNDLE_PATH}" ]]; then
  echo "error: bundle file not found: ${BUNDLE_PATH}" >&2
  exit 1
fi

DEP_BUNDLE_PATH=""
if [[ -f "${DEP_MANIFEST_PATH}" ]]; then
  DEP_BUNDLE_PATH="$(rg -n '^- Bundle: `' "${DEP_MANIFEST_PATH}" | sed -E 's/.*`([^`]+)`.*/\1/' || true)"
fi

TMP_DIR="$(mktemp -d)"

cleanup() {
  if [[ "${KEEP_CLONE}" == "true" ]]; then
    echo "[info] keeping integration-probe temp dir: ${TMP_DIR}"
    return
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

REPORT_TMP="${TMP_DIR}/report.md"
touch "${REPORT_TMP}"

append_section() {
  local case_name="$1"
  local clone_dir="$2"
  local overlay_mode="$3"

  local base_sha
  local changed_total
  local patch_check_status
  local patch_apply_status
  local smoke_status
  local pytest_status
  local smoke_error_excerpt
  local pytest_error_excerpt

  base_sha="$(cat "${clone_dir}/.probe_base_sha")"
  changed_total="$(cat "${clone_dir}/.probe_changed_total")"
  patch_check_status="$(cat "${clone_dir}/.probe_patch_check_status")"
  patch_apply_status="$(cat "${clone_dir}/.probe_patch_apply_status")"
  smoke_status="$(cat "${clone_dir}/.probe_smoke_status")"
  pytest_status="$(cat "${clone_dir}/.probe_pytest_status")"
  smoke_error_excerpt="$(cat "${clone_dir}/.probe_smoke_error_excerpt")"
  pytest_error_excerpt="$(cat "${clone_dir}/.probe_pytest_error_excerpt")"

  {
    echo "## Case: ${case_name}"
    echo
    echo "- Overlay mode: \`${overlay_mode}\`"
    echo "- Base SHA: \`${base_sha}\`"
    echo "- changed paths after replay+patch: \`${changed_total}\`"
    echo "- patch check: \`${patch_check_status}\`"
    echo "- patch apply: \`${patch_apply_status}\`"
    echo "- app smoke: \`${smoke_status}\`"
    echo "- pytest health: \`${pytest_status}\`"
    if [[ -n "${smoke_error_excerpt}" ]]; then
      echo
      echo "### Smoke error excerpt"
      echo
      echo '```'
      echo "${smoke_error_excerpt}"
      echo '```'
    fi
    if [[ -n "${pytest_error_excerpt}" ]]; then
      echo
      echo "### Pytest error excerpt"
      echo
      echo '```'
      echo "${pytest_error_excerpt}"
      echo '```'
    fi
    echo
  } >> "${REPORT_TMP}"
}

run_case() {
  local case_name="$1"
  local overlay_mode="$2"
  local clone_dir="${TMP_DIR}/${case_name}"
  local patch_check_status="ok"
  local patch_apply_status="applied"

  git clone --quiet "${ROOT_DIR}" "${clone_dir}"
  pushd "${clone_dir}" >/dev/null
  git checkout -B "${LANDING_BRANCH}" "${TARGET_SHA}" >/dev/null
  git rev-parse HEAD > "${clone_dir}/.probe_base_sha"

  tar -xzf "${ROOT_DIR}/${BUNDLE_PATH}" -C "${clone_dir}"

  if ! git apply --check "${ROOT_DIR}/${PATCH_PATH}" >"${clone_dir}/patch_check.stdout" 2>"${clone_dir}/patch_check.stderr"; then
    patch_check_status="failed"
    patch_apply_status="skipped"
  else
    git apply "${ROOT_DIR}/${PATCH_PATH}"
  fi

  if [[ "${overlay_mode}" == "graph-runtime" || "${overlay_mode}" == "graph-runtime-runner-shim" ]]; then
    if [[ -n "${DEP_BUNDLE_PATH}" && -f "${ROOT_DIR}/${DEP_BUNDLE_PATH}" ]]; then
      tar -xzf "${ROOT_DIR}/${DEP_BUNDLE_PATH}" -C "${clone_dir}"
    else
      cp -R "${ROOT_DIR}/core/framework/runtime" "${clone_dir}/core/framework/"
      cp -R "${ROOT_DIR}/core/framework/graph" "${clone_dir}/core/framework/"
      cp -R "${ROOT_DIR}/core/framework/runner" "${clone_dir}/core/framework/"
      cp "${ROOT_DIR}/core/framework/server/routes_graphs.py" "${clone_dir}/core/framework/server/routes_graphs.py"
    fi
  fi
  if [[ "${overlay_mode}" == "graph-runtime-runner-shim" ]]; then
    cat <<'PY' > "${clone_dir}/core/framework/runner/__init__.py"
"""Agent Runner package exports (probe shim)."""

from framework.runner.mcp_registry import MCPRegistry
from framework.runner.protocol import (
    AgentMessage,
    CapabilityLevel,
    CapabilityResponse,
    MessageType,
    OrchestratorResult,
)
from framework.runner.tool_registry import ToolRegistry, tool

__all__ = [
    "ToolRegistry",
    "MCPRegistry",
    "tool",
    "AgentMessage",
    "MessageType",
    "CapabilityLevel",
    "CapabilityResponse",
    "OrchestratorResult",
]
PY
  fi

  git status --short | sed '/^$/d' | wc -l | tr -d ' ' > "${clone_dir}/.probe_changed_total"
  printf "%s" "${patch_check_status}" > "${clone_dir}/.probe_patch_check_status"
  printf "%s" "${patch_apply_status}" > "${clone_dir}/.probe_patch_apply_status"

  local smoke_status="ok"
  if ! uv run --package framework python - <<'PY' >"${clone_dir}/smoke.stdout" 2>"${clone_dir}/smoke.stderr"; then
from framework.server.app import create_app

app = create_app()
paths: list[str] = []
for resource in app.router.resources():
    info = resource.get_info()
    path = info.get("path")
    if path:
        paths.append(path)
        continue
    formatter = info.get("formatter")
    if formatter is not None:
        pattern = getattr(formatter, "_pattern", None)
        paths.append(pattern or str(formatter))
required = [
    "/api/health",
    "/api/projects",
    "/api/projects/{project_id}/autonomous/execute-next",
    "/api/telegram/bridge/status",
]
missing = [item for item in required if item not in paths]
if missing:
    raise SystemExit(f"missing routes: {missing}")
print("route smoke ok")
PY
    smoke_status="failed"
  fi
  printf "%s" "${smoke_status}" > "${clone_dir}/.probe_smoke_status"

  local pytest_status="ok"
  if ! uv run --package framework pytest core/framework/server/tests/test_api.py -k "health" -q >"${clone_dir}/pytest.stdout" 2>"${clone_dir}/pytest.stderr"; then
    pytest_status="failed"
  fi
  printf "%s" "${pytest_status}" > "${clone_dir}/.probe_pytest_status"

  {
    rg -n "ModuleNotFoundError|ImportError|NameError|SyntaxError|Traceback|missing routes" \
      "${clone_dir}/smoke.stderr" "${clone_dir}/smoke.stdout" 2>/dev/null || true
  } | head -n 40 > "${clone_dir}/.probe_smoke_error_excerpt"

  {
    rg -n "ModuleNotFoundError|ImportError|NameError|SyntaxError|Traceback|ERROR|FAILED|E\\s+" \
      "${clone_dir}/pytest.stderr" "${clone_dir}/pytest.stdout" 2>/dev/null || true
  } | head -n 60 > "${clone_dir}/.probe_pytest_error_excerpt"

  popd >/dev/null
  append_section "${case_name}" "${clone_dir}" "${overlay_mode}"
}

echo "== Overlap Batch A Integration Probe =="
echo "target_ref=${TARGET_REF}"
echo "target_sha=${TARGET_SHA}"
echo "landing_branch=${LANDING_BRANCH}"
echo "bundle=${BUNDLE_PATH}"
echo "patch=${PATCH_PATH}"
if [[ -n "${DEP_BUNDLE_PATH}" ]]; then
  echo "dependency_bundle=${DEP_BUNDLE_PATH}"
else
  echo "dependency_bundle=<inline copy fallback>"
fi

{
  echo "# Overlap Batch A Integration Probe Snapshot"
  echo
  echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Target ref: ${TARGET_REF}"
  echo "- Target SHA: ${TARGET_SHA}"
  echo "- Landing branch: ${LANDING_BRANCH}"
  echo "- Replay bundle: \`${BUNDLE_PATH}\`"
  echo "- Focus patch: \`${PATCH_PATH}\`"
  if [[ -n "${DEP_BUNDLE_PATH}" ]]; then
    echo "- Dependency bundle: \`${DEP_BUNDLE_PATH}\`"
  else
    echo "- Dependency bundle: _not configured_ (inline copy fallback)"
  fi
  echo
} > "${REPORT_TMP}"

run_case "baseline-no-overlay" "none"
run_case "overlay-graph-runtime" "graph-runtime"
run_case "overlay-graph-runtime-runner-shim" "graph-runtime-runner-shim"

cp "${REPORT_TMP}" "${REPORT_PATH}"
echo "[ok] wrote ${REPORT_PATH}"

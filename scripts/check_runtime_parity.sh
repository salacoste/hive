#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${HIVE_BASE_URL:-http://localhost:${HIVE_CORE_PORT:-8787}}"
TIMEOUT_SEC="${HIVE_RUNTIME_PARITY_TIMEOUT:-15}"
PROJECT_ID="${HIVE_RUNTIME_PARITY_PROJECT_ID:-default}"
CORE_PORT="${HIVE_CORE_PORT:-8787}"

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required" >&2
  exit 2
fi

HAS_CURL=1
if ! command -v curl >/dev/null 2>&1; then
  HAS_CURL=0
  echo "[warn] curl not found, falling back to uv+urllib for HTTP requests" >&2
fi

fail=0

http_get() {
  local url="$1"
  if [[ "$HAS_CURL" -eq 1 ]]; then
    curl -sS --max-time "$TIMEOUT_SEC" "$url"
    return
  fi
  uv run --no-project python - "$url" "$TIMEOUT_SEC" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
timeout = float(sys.argv[2])
with urllib.request.urlopen(url, timeout=timeout) as resp:
    sys.stdout.write(resp.read().decode("utf-8", errors="replace"))
PY
}

http_post_json() {
  local url="$1"
  local payload="$2"
  if [[ "$HAS_CURL" -eq 1 ]]; then
    curl -sS --max-time "$TIMEOUT_SEC" -X POST -H 'Content-Type: application/json' -d "$payload" "$url"
    return
  fi
  uv run --no-project python - "$url" "$payload" "$TIMEOUT_SEC" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
payload = sys.argv[2].encode("utf-8")
timeout = float(sys.argv[3])
req = urllib.request.Request(
    url,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=timeout) as resp:
    sys.stdout.write(resp.read().decode("utf-8", errors="replace"))
PY
}

check_json_endpoint() {
  local name="$1"
  local url="$2"
  local resp
  resp=$(http_get "$url" || true)
  if [[ -z "$resp" ]]; then
    echo "[fail] $name: empty response" >&2
    fail=$((fail + 1))
    return
  fi
  if ! echo "$resp" | jq . >/dev/null 2>&1; then
    echo "[fail] $name: response is not valid JSON" >&2
    fail=$((fail + 1))
    return
  fi
  echo "[ok] $name: valid JSON"
}

check_json_post_endpoint() {
  local name="$1"
  local url="$2"
  local payload="$3"
  local resp
  resp=$(http_post_json "$url" "$payload" || true)
  if [[ -z "$resp" ]]; then
    echo "[fail] $name: empty response" >&2
    fail=$((fail + 1))
    return
  fi
  if ! echo "$resp" | jq . >/dev/null 2>&1; then
    echo "[fail] $name: response is not valid JSON" >&2
    fail=$((fail + 1))
    return
  fi
  echo "[ok] $name: valid JSON"
}

resolve_base_url() {
  if [[ -n "${HIVE_BASE_URL:-}" ]]; then
    echo "$HIVE_BASE_URL"
    return 0
  fi

  local candidates=(
    "http://localhost:${CORE_PORT}"
    "http://hive-core:${CORE_PORT}"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if http_get "${candidate}/api/health" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done

  # Keep historical default if health probes are unreachable; downstream checks
  # will emit precise endpoint errors.
  echo "http://localhost:${CORE_PORT}"
}

BASE_URL="$(resolve_base_url)"
echo "[info] runtime parity base_url=${BASE_URL}"

check_json_endpoint "autonomous ops status" \
  "$BASE_URL/api/autonomous/ops/status?project_id=${PROJECT_ID}&include_runs=true"
check_json_endpoint "llm queue status" \
  "$BASE_URL/api/llm/queue/status"
check_json_endpoint "telegram bridge status" \
  "$BASE_URL/api/telegram/bridge/status"
check_json_endpoint "telegram bridge bindings" \
  "$BASE_URL/api/telegram/bridge/bindings"
check_json_post_endpoint "run-cycle compact report" \
  "$BASE_URL/api/autonomous/loop/run-cycle/report" \
  "{\"project_ids\":[\"${PROJECT_ID}\"],\"auto_start\":false,\"max_steps_per_project\":1}"

ops_resp=$(http_get "$BASE_URL/api/autonomous/ops/status?project_id=${PROJECT_ID}&include_runs=true" || true)
if echo "$ops_resp" | jq -e '.alerts and (.alerts|type=="object") and .loop and (.loop|type=="object") and .summary and (.summary|type=="object")' >/dev/null 2>&1; then
  echo "[ok] autonomous ops status contract includes alerts/loop/summary objects"
else
  echo "[fail] autonomous ops status contract drift: missing alerts or loop object" >&2
  fail=$((fail + 1))
fi

if echo "$ops_resp" | jq -e '.summary.include_runs != null and .summary.project_filter != null' >/dev/null 2>&1; then
  echo "[ok] autonomous ops summary includes include_runs and project_filter"
else
  echo "[fail] autonomous ops summary missing include_runs/project_filter" >&2
  fail=$((fail + 1))
fi

llm_resp=$(http_get "$BASE_URL/api/llm/queue/status" || true)
if echo "$llm_resp" | jq -e '.status == "ok" and (.queue|type=="object") and (.queue.limits|type=="object") and (.queue.backoff|type=="object") and (.queue.sync|type=="object") and (.queue.async|type=="object") and (.fallback|type=="object") and (.fallback.policy|type=="object") and (.fallback.history_limit|type=="number") and (.fallback.recent_attempt_chains|type=="array")' >/dev/null 2>&1; then
  echo "[ok] llm queue status contract includes queue + fallback snapshots"
else
  echo "[fail] llm queue status contract drift: missing queue/fallback fields" >&2
  fail=$((fail + 1))
fi

bridge_bindings_resp=$(http_get "$BASE_URL/api/telegram/bridge/bindings" || true)
if echo "$bridge_bindings_resp" | jq -e '(.status=="ok" or .status=="disabled") and (.bindings|type=="array") and (.known_chats_total|type=="number") and (.bound_chats_total|type=="number") and (.sessions_with_bound_chats_total|type=="number")' >/dev/null 2>&1; then
  echo "[ok] telegram bridge bindings contract includes binding counters"
else
  echo "[fail] telegram bridge bindings contract drift: missing binding snapshot fields" >&2
  fail=$((fail + 1))
fi

if (( fail > 0 )); then
  echo "runtime parity check failed: $fail issue(s)" >&2
  exit 1
fi

echo "runtime parity check passed"

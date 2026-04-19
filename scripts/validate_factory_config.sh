#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTOMATION_DIR="$ROOT_DIR/automation"

POLICY_FILE="$AUTOMATION_DIR/hive.factory-policy.yaml"
MANIFEST_FILE="$AUTOMATION_DIR/hive.manifest.yaml"
TASK_FILE="$AUTOMATION_DIR/hive.task.yaml"

fail=0

require_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "[FAIL] missing file: $file"
    fail=1
  else
    echo "[OK] file: $file"
  fi
}

require_pattern() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if rg -q "$pattern" "$file"; then
    echo "[OK] $label"
  else
    echo "[FAIL] $label (pattern: $pattern)"
    fail=1
  fi
}

require_file "$POLICY_FILE"
require_file "$MANIFEST_FILE"
require_file "$TASK_FILE"

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

require_pattern "$POLICY_FILE" "^schema_version:" "policy schema version present"
require_pattern "$POLICY_FILE" "^factory:" "policy factory block present"
require_pattern "$POLICY_FILE" "default_risk_tier:" "policy default risk present"

require_pattern "$MANIFEST_FILE" "^schema_version:" "manifest schema version present"
require_pattern "$MANIFEST_FILE" "^repository:" "manifest repository block present"
require_pattern "$MANIFEST_FILE" "^automation:" "manifest automation block present"

require_pattern "$TASK_FILE" "^schema_version:" "task schema version present"
require_pattern "$TASK_FILE" "^task:" "task block present"
require_pattern "$TASK_FILE" "^repository:" "task repository block present"
require_pattern "$TASK_FILE" "^acceptance_criteria:" "task acceptance criteria present"

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "[OK] factory config validation passed"


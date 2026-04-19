#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_DIR="$ROOT_DIR/docs/autonomous-factory/templates"
AUTOMATION_DIR="$ROOT_DIR/automation"

mkdir -p "$AUTOMATION_DIR"

copy_if_missing() {
  local src="$1"
  local dst="$2"
  if [[ -f "$dst" ]]; then
    echo "[SKIP] exists: $dst"
  else
    cp "$src" "$dst"
    echo "[OK] created: $dst"
  fi
}

copy_if_missing "$TEMPLATE_DIR/factory-policy.yaml" "$AUTOMATION_DIR/hive.factory-policy.yaml"
copy_if_missing "$TEMPLATE_DIR/repo-automation-manifest.yaml" "$AUTOMATION_DIR/hive.manifest.yaml"
copy_if_missing "$TEMPLATE_DIR/task-brief.yaml" "$AUTOMATION_DIR/hive.task.yaml"

echo
echo "Next:"
echo "1) Fill values in automation/hive.manifest.yaml"
echo "2) Fill values in automation/hive.factory-policy.yaml"
echo "3) Create task in automation/hive.task.yaml"
echo "4) Run scripts/validate_factory_config.sh"


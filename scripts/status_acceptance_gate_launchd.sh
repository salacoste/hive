#!/usr/bin/env bash
set -euo pipefail

PLIST_NAME="com.hive.acceptance-gate"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

if [[ ! -f "$PLIST_PATH" ]]; then
  echo "not-installed"
  exit 0
fi

echo "installed: $PLIST_PATH"
launchctl list | grep "$PLIST_NAME" || echo "loaded: no (not in launchctl list)"

echo "configured env:"
plutil -extract EnvironmentVariables.HIVE_ACCEPTANCE_PROFILE raw -o - "$PLIST_PATH" 2>/dev/null | sed 's/^/  HIVE_ACCEPTANCE_PROFILE=/' || true
plutil -extract EnvironmentVariables.HIVE_ACCEPTANCE_SKIP_CHECKLIST raw -o - "$PLIST_PATH" 2>/dev/null | sed 's/^/  HIVE_ACCEPTANCE_SKIP_CHECKLIST=/' || true
plutil -extract EnvironmentVariables.HIVE_ACCEPTANCE_SKIP_TELEGRAM raw -o - "$PLIST_PATH" 2>/dev/null | sed 's/^/  HIVE_ACCEPTANCE_SKIP_TELEGRAM=/' || true
plutil -extract EnvironmentVariables.HIVE_ACCEPTANCE_ENFORCE_HISTORY raw -o - "$PLIST_PATH" 2>/dev/null | sed 's/^/  HIVE_ACCEPTANCE_ENFORCE_HISTORY=/' || true
plutil -extract EnvironmentVariables.HIVE_ACCEPTANCE_HISTORY_MAX_FAIL raw -o - "$PLIST_PATH" 2>/dev/null | sed 's/^/  HIVE_ACCEPTANCE_HISTORY_MAX_FAIL=/' || true
plutil -extract EnvironmentVariables.HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE raw -o - "$PLIST_PATH" 2>/dev/null | sed 's/^/  HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE=/' || true

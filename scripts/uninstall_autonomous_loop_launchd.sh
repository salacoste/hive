#!/usr/bin/env bash
set -euo pipefail

PLIST_NAME="com.hive.autonomous-loop"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

if [[ -f "$PLIST_PATH" ]]; then
  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  rm -f "$PLIST_PATH"
  echo "Uninstalled ${PLIST_NAME}"
else
  echo "Not installed: ${PLIST_PATH}"
fi

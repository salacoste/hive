#!/usr/bin/env bash
set -euo pipefail

PLIST_NAME="com.hive.google-canary"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

if [[ ! -f "$PLIST_PATH" ]]; then
  echo "not-installed"
  exit 0
fi

launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"
echo "Removed ${PLIST_NAME}"

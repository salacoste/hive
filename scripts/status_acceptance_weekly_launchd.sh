#!/usr/bin/env bash
set -euo pipefail

PLIST_NAME="com.hive.acceptance-weekly"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

if [[ ! -f "$PLIST_PATH" ]]; then
  echo "not-installed"
  exit 0
fi

echo "installed: $PLIST_PATH"
launchctl list | grep "$PLIST_NAME" || echo "loaded: no (not in launchctl list)"

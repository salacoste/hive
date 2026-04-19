#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${HIVE_LAUNCHD_WORKDIR:-$HOME}"
PLIST_NAME="com.hive.autonomous-loop"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_DIR="$ROOT_DIR/.logs"
LOG_OUT="$LOG_DIR/autonomous-loop.out.log"
LOG_ERR="$LOG_DIR/autonomous-loop.err.log"
INTERVAL="${HIVE_AUTONOMOUS_LOOP_INTERVAL:-120}"

if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [[ "$INTERVAL" -lt 15 ]]; then
  echo "error: HIVE_AUTONOMOUS_LOOP_INTERVAL must be integer >= 15 (seconds)" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
if [[ ! -d "$WORK_DIR" ]]; then
  echo "error: HIVE_LAUNCHD_WORKDIR does not exist: $WORK_DIR" >&2
  exit 1
fi

cat >"$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_NAME}</string>

  <key>WorkingDirectory</key>
  <string>${WORK_DIR}</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd '${ROOT_DIR}' &amp;&amp; bash ./scripts/autonomous_loop_tick.sh</string>
  </array>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>

  <key>RunAtLoad</key>
  <true/>

  <key>StartInterval</key>
  <integer>${INTERVAL}</integer>

  <key>StandardOutPath</key>
  <string>${LOG_OUT}</string>
  <key>StandardErrorPath</key>
  <string>${LOG_ERR}</string>
</dict>
</plist>
PLIST

launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$PLIST_PATH"

echo "Installed ${PLIST_NAME}"
echo "plist: ${PLIST_PATH}"
echo "interval: ${INTERVAL}s"
echo "working_dir: ${WORK_DIR}"
echo "logs:"
echo "  - ${LOG_OUT}"
echo "  - ${LOG_ERR}"

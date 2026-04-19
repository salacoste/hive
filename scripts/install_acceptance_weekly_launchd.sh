#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${HIVE_LAUNCHD_WORKDIR:-$HOME}"
PLIST_NAME="com.hive.acceptance-weekly"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_DIR="$ROOT_DIR/.logs"
LOG_OUT="$LOG_DIR/acceptance-weekly.out.log"
LOG_ERR="$LOG_DIR/acceptance-weekly.err.log"
INTERVAL="${HIVE_ACCEPTANCE_WEEKLY_INTERVAL:-604800}"

if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [[ "$INTERVAL" -lt 86400 ]]; then
  echo "error: HIVE_ACCEPTANCE_WEEKLY_INTERVAL must be integer >= 86400 (seconds)" >&2
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
    <string>cd '${ROOT_DIR}' &amp;&amp; bash ./scripts/acceptance_weekly_maintenance.sh</string>
  </array>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>HIVE_ACCEPTANCE_ENFORCE_HISTORY</key>
    <string>${HIVE_ACCEPTANCE_ENFORCE_HISTORY:-true}</string>
    <key>HIVE_ACCEPTANCE_REPORT_PRUNE_APPLY</key>
    <string>${HIVE_ACCEPTANCE_REPORT_PRUNE_APPLY:-false}</string>
    <key>HIVE_ACCEPTANCE_REPORT_KEEP</key>
    <string>${HIVE_ACCEPTANCE_REPORT_KEEP:-50}</string>
    <key>HIVE_ACCEPTANCE_DIGEST_DAYS</key>
    <string>${HIVE_ACCEPTANCE_DIGEST_DAYS:-7}</string>
    <key>HIVE_ACCEPTANCE_DIGEST_LIMIT</key>
    <string>${HIVE_ACCEPTANCE_DIGEST_LIMIT:-20}</string>
    <key>HIVE_ACCEPTANCE_HISTORY_MAX_FAIL</key>
    <string>${HIVE_ACCEPTANCE_HISTORY_MAX_FAIL:-0}</string>
    <key>HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE</key>
    <string>${HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE:-1.0}</string>
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

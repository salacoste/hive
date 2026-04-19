#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${HIVE_LAUNCHD_WORKDIR:-$HOME}"
PLIST_NAME="com.hive.google-canary"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_DIR="$ROOT_DIR/.logs"
LOG_OUT="$LOG_DIR/google-canary.out.log"
LOG_ERR="$LOG_DIR/google-canary.err.log"
INTERVAL="${HIVE_GOOGLE_CANARY_INTERVAL_SECONDS:-1800}"
DOTENV_PATH="${HIVE_GOOGLE_CANARY_DOTENV:-.env}"
ARTIFACT_DIR="${HIVE_GOOGLE_CANARY_ARTIFACT_DIR:-docs/ops/google-canary}"
WRITE_MODE="${HIVE_GOOGLE_CANARY_WRITE_MODE:-false}"

if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [[ "$INTERVAL" -lt 300 ]]; then
  echo "error: HIVE_GOOGLE_CANARY_INTERVAL_SECONDS must be integer >= 300" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
if [[ ! -d "$WORK_DIR" ]]; then
  echo "error: HIVE_LAUNCHD_WORKDIR does not exist: $WORK_DIR" >&2
  exit 1
fi

EXTRA_ARGS=""
if [[ "$WRITE_MODE" == "true" || "$WRITE_MODE" == "1" ]]; then
  EXTRA_ARGS=" --write"
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
    <string>cd '${ROOT_DIR}' &amp;&amp; uv run python ./scripts/google_mcp_canary.py --dotenv '${DOTENV_PATH}' --artifact-dir '${ARTIFACT_DIR}'${EXTRA_ARGS}</string>
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
echo "write_mode: ${WRITE_MODE}"
echo "logs:"
echo "  - ${LOG_OUT}"
echo "  - ${LOG_ERR}"

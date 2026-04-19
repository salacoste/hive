#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${HIVE_LAUNCHD_WORKDIR:-$HOME}"
PLIST_NAME="com.hive.acceptance-gate"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_DIR="$ROOT_DIR/.logs"
LOG_OUT="$LOG_DIR/acceptance-gate.out.log"
LOG_ERR="$LOG_DIR/acceptance-gate.err.log"
INTERVAL="${HIVE_ACCEPTANCE_GATE_INTERVAL:-3600}"
PROFILE="${HIVE_ACCEPTANCE_PROFILE:-balanced}"

case "$PROFILE" in
  balanced)
    DEFAULT_SKIP_CHECKLIST="true"
    DEFAULT_SKIP_TELEGRAM="false"
    DEFAULT_REPORT_KEEP="50"
    DEFAULT_REPORT_PRUNE_APPLY="false"
    DEFAULT_DIGEST_DAYS="7"
    DEFAULT_DIGEST_LIMIT="20"
    DEFAULT_ENFORCE_HISTORY="false"
    DEFAULT_HISTORY_MAX_FAIL="0"
    DEFAULT_HISTORY_MIN_PASS_RATE="1.0"
    ;;
  strict)
    DEFAULT_SKIP_CHECKLIST="true"
    DEFAULT_SKIP_TELEGRAM="false"
    DEFAULT_REPORT_KEEP="50"
    DEFAULT_REPORT_PRUNE_APPLY="false"
    DEFAULT_DIGEST_DAYS="7"
    DEFAULT_DIGEST_LIMIT="30"
    DEFAULT_ENFORCE_HISTORY="true"
    DEFAULT_HISTORY_MAX_FAIL="0"
    DEFAULT_HISTORY_MIN_PASS_RATE="1.0"
    ;;
  *)
    echo "error: HIVE_ACCEPTANCE_PROFILE must be one of: balanced, strict" >&2
    exit 1
    ;;
esac

SKIP_CHECKLIST="${HIVE_ACCEPTANCE_SKIP_CHECKLIST:-$DEFAULT_SKIP_CHECKLIST}"
SKIP_TELEGRAM="${HIVE_ACCEPTANCE_SKIP_TELEGRAM:-$DEFAULT_SKIP_TELEGRAM}"
REPORT_KEEP="${HIVE_ACCEPTANCE_REPORT_KEEP:-$DEFAULT_REPORT_KEEP}"
REPORT_PRUNE_APPLY="${HIVE_ACCEPTANCE_REPORT_PRUNE_APPLY:-$DEFAULT_REPORT_PRUNE_APPLY}"
DIGEST_DAYS="${HIVE_ACCEPTANCE_DIGEST_DAYS:-$DEFAULT_DIGEST_DAYS}"
DIGEST_LIMIT="${HIVE_ACCEPTANCE_DIGEST_LIMIT:-$DEFAULT_DIGEST_LIMIT}"
DIGEST_JSON_PATH="${HIVE_ACCEPTANCE_DIGEST_JSON_PATH:-docs/ops/acceptance-reports/digest-latest.json}"
DIGEST_MD_PATH="${HIVE_ACCEPTANCE_DIGEST_MD_PATH:-docs/ops/acceptance-reports/digest-latest.md}"
ENFORCE_HISTORY="${HIVE_ACCEPTANCE_ENFORCE_HISTORY:-$DEFAULT_ENFORCE_HISTORY}"
HISTORY_MAX_FAIL="${HIVE_ACCEPTANCE_HISTORY_MAX_FAIL:-$DEFAULT_HISTORY_MAX_FAIL}"
HISTORY_MIN_PASS_RATE="${HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE:-$DEFAULT_HISTORY_MIN_PASS_RATE}"

if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [[ "$INTERVAL" -lt 300 ]]; then
  echo "error: HIVE_ACCEPTANCE_GATE_INTERVAL must be integer >= 300 (seconds)" >&2
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
    <string>cd '${ROOT_DIR}' &amp;&amp; bash ./scripts/autonomous_acceptance_gate.sh</string>
  </array>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>HIVE_ACCEPTANCE_PROFILE</key>
    <string>${PROFILE}</string>
    <key>HIVE_ACCEPTANCE_SKIP_CHECKLIST</key>
    <string>${SKIP_CHECKLIST}</string>
    <key>HIVE_ACCEPTANCE_SKIP_TELEGRAM</key>
    <string>${SKIP_TELEGRAM}</string>
    <key>HIVE_ACCEPTANCE_REPORT_KEEP</key>
    <string>${REPORT_KEEP}</string>
    <key>HIVE_ACCEPTANCE_REPORT_PRUNE_APPLY</key>
    <string>${REPORT_PRUNE_APPLY}</string>
    <key>HIVE_ACCEPTANCE_DIGEST_DAYS</key>
    <string>${DIGEST_DAYS}</string>
    <key>HIVE_ACCEPTANCE_DIGEST_LIMIT</key>
    <string>${DIGEST_LIMIT}</string>
    <key>HIVE_ACCEPTANCE_DIGEST_JSON_PATH</key>
    <string>${DIGEST_JSON_PATH}</string>
    <key>HIVE_ACCEPTANCE_DIGEST_MD_PATH</key>
    <string>${DIGEST_MD_PATH}</string>
    <key>HIVE_ACCEPTANCE_ENFORCE_HISTORY</key>
    <string>${ENFORCE_HISTORY}</string>
    <key>HIVE_ACCEPTANCE_HISTORY_MAX_FAIL</key>
    <string>${HISTORY_MAX_FAIL}</string>
    <key>HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE</key>
    <string>${HISTORY_MIN_PASS_RATE}</string>
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
echo "env:"
echo "  - HIVE_ACCEPTANCE_PROFILE=${PROFILE}"
echo "  - HIVE_ACCEPTANCE_SKIP_CHECKLIST=${SKIP_CHECKLIST}"
echo "  - HIVE_ACCEPTANCE_SKIP_TELEGRAM=${SKIP_TELEGRAM}"
echo "  - HIVE_ACCEPTANCE_REPORT_KEEP=${REPORT_KEEP}"
echo "  - HIVE_ACCEPTANCE_REPORT_PRUNE_APPLY=${REPORT_PRUNE_APPLY}"
echo "  - HIVE_ACCEPTANCE_DIGEST_DAYS=${DIGEST_DAYS}"
echo "  - HIVE_ACCEPTANCE_DIGEST_LIMIT=${DIGEST_LIMIT}"
echo "  - HIVE_ACCEPTANCE_DIGEST_JSON_PATH=${DIGEST_JSON_PATH}"
echo "  - HIVE_ACCEPTANCE_DIGEST_MD_PATH=${DIGEST_MD_PATH}"
echo "  - HIVE_ACCEPTANCE_ENFORCE_HISTORY=${ENFORCE_HISTORY}"
echo "  - HIVE_ACCEPTANCE_HISTORY_MAX_FAIL=${HISTORY_MAX_FAIL}"
echo "  - HIVE_ACCEPTANCE_HISTORY_MIN_PASS_RATE=${HISTORY_MIN_PASS_RATE}"
echo "logs:"
echo "  - ${LOG_OUT}"
echo "  - ${LOG_ERR}"

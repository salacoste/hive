#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/_cron_job_lib.sh"

MARKER="HIVE_CRON_GOOGLE_CANARY"
CRON_EXPR="${HIVE_GOOGLE_CANARY_CRON_EXPR:-*/30 * * * *}"
LOG_DIR="$ROOT_DIR/.logs"
LOG_FILE="$LOG_DIR/google-canary.cron.log"
SCRIPT_PATH="$ROOT_DIR/scripts/google_mcp_canary.py"
DOTENV_PATH="${HIVE_GOOGLE_CANARY_DOTENV:-.env}"
WRITE_MODE="${HIVE_GOOGLE_CANARY_WRITE_MODE:-false}"
ARTIFACT_DIR="${HIVE_GOOGLE_CANARY_ARTIFACT_DIR:-docs/ops/google-canary}"

hive_cron_require_crontab
hive_cron_validate_expr "$CRON_EXPR"
mkdir -p "$LOG_DIR"

EXTRA=""
if [[ "$WRITE_MODE" == "true" || "$WRITE_MODE" == "1" ]]; then
  EXTRA=" --write"
fi

CMD="/bin/bash -lc \"cd $(hive_cron_q "$ROOT_DIR") && uv run python $(hive_cron_q "$SCRIPT_PATH") --dotenv $(hive_cron_q "$DOTENV_PATH") --artifact-dir $(hive_cron_q "$ARTIFACT_DIR")${EXTRA} >> $(hive_cron_q "$LOG_FILE") 2>&1\""
hive_cron_upsert "$MARKER" "$CRON_EXPR" "$CMD"

echo "Installed $MARKER"
echo "cron: $CRON_EXPR"
echo "write_mode: $WRITE_MODE"
echo "artifact_dir: $ARTIFACT_DIR"
echo "log: $LOG_FILE"

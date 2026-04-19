#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/_cron_job_lib.sh"

MARKER="HIVE_CRON_AUTONOMOUS_LOOP"
CRON_EXPR="${HIVE_AUTONOMOUS_LOOP_CRON_EXPR:-*/2 * * * *}"
LOG_DIR="$ROOT_DIR/.logs"
LOG_FILE="$LOG_DIR/autonomous-loop.cron.log"
SCRIPT_PATH="$ROOT_DIR/scripts/autonomous_loop_tick.sh"

hive_cron_require_crontab
hive_cron_validate_expr "$CRON_EXPR"
mkdir -p "$LOG_DIR"

AUTO_START="${HIVE_AUTONOMOUS_AUTO_START:-true}"
USE_TICK_ALL="${HIVE_AUTONOMOUS_USE_TICK_ALL:-true}"
USE_RUN_CYCLE="${HIVE_AUTONOMOUS_USE_RUN_CYCLE:-true}"
MAX_STEPS="${HIVE_AUTONOMOUS_MAX_STEPS_PER_PROJECT:-3}"
TIMEOUT_SEC="${HIVE_AUTONOMOUS_TICK_TIMEOUT:-20}"
PROJECT_IDS="${HIVE_AUTONOMOUS_PROJECT_IDS:-}"

CMD="HIVE_AUTONOMOUS_AUTO_START=$(hive_cron_q "$AUTO_START") \
HIVE_AUTONOMOUS_USE_TICK_ALL=$(hive_cron_q "$USE_TICK_ALL") \
HIVE_AUTONOMOUS_USE_RUN_CYCLE=$(hive_cron_q "$USE_RUN_CYCLE") \
HIVE_AUTONOMOUS_MAX_STEPS_PER_PROJECT=$(hive_cron_q "$MAX_STEPS") \
HIVE_AUTONOMOUS_TICK_TIMEOUT=$(hive_cron_q "$TIMEOUT_SEC") \
HIVE_AUTONOMOUS_PROJECT_IDS=$(hive_cron_q "$PROJECT_IDS") \
/bin/bash $(hive_cron_q "$SCRIPT_PATH") >> $(hive_cron_q "$LOG_FILE") 2>&1"

hive_cron_upsert "$MARKER" "$CRON_EXPR" "$CMD"

echo "Installed $MARKER"
echo "cron: $CRON_EXPR"
echo "log: $LOG_FILE"
echo "script: $SCRIPT_PATH"


#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/_cron_job_lib.sh"

MARKER="HIVE_CRON_GOOGLE_CANARY"
hive_cron_require_crontab
hive_cron_remove "$MARKER"
echo "Removed $MARKER"

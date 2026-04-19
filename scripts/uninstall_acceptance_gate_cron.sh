#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/_cron_job_lib.sh"

MARKER="HIVE_CRON_ACCEPTANCE_GATE"

hive_cron_require_crontab
line="$(hive_cron_get_line "$MARKER")"
if [[ -z "$line" ]]; then
  echo "Not installed: $MARKER"
  exit 0
fi

hive_cron_remove "$MARKER"
echo "Uninstalled $MARKER"


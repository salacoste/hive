#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/_cron_job_lib.sh"

MARKER="HIVE_CRON_GOOGLE_CANARY"
line="$(hive_cron_get_line "$MARKER")"
if [[ -z "$line" ]]; then
  echo "not-installed"
  exit 0
fi

echo "installed"
echo "$line"

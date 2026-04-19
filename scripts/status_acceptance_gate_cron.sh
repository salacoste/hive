#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/_cron_job_lib.sh"

MARKER="HIVE_CRON_ACCEPTANCE_GATE"

if ! hive_cron_has_crontab; then
  echo "not-supported: crontab not found"
  exit 0
fi

line="$(hive_cron_get_line "$MARKER")"
if [[ -z "$line" ]]; then
  echo "not-installed"
  exit 0
fi

echo "installed: $MARKER"
echo "line: $line"
echo "configured env:"
echo "$line" | tr ' ' '\n' | grep -E '^HIVE_ACCEPTANCE_[A-Z_]+=.*' | sed 's/^/  /' || true

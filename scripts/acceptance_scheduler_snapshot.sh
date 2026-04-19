#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TAIL_LINES="${HIVE_ACCEPTANCE_SNAPSHOT_TAIL_LINES:-20}"
if ! [[ "$TAIL_LINES" =~ ^[0-9]+$ ]] || [[ "$TAIL_LINES" -lt 0 ]]; then
  echo "error: HIVE_ACCEPTANCE_SNAPSHOT_TAIL_LINES must be integer >= 0" >&2
  exit 1
fi

echo "== Acceptance Scheduler Snapshot =="
echo "tail_lines=$TAIL_LINES"

echo ""
echo "-- hourly gate scheduler (launchd) --"
./scripts/status_acceptance_gate_launchd.sh || true

echo ""
echo "-- hourly gate scheduler (cron) --"
./scripts/status_acceptance_gate_cron.sh || true

echo ""
echo "-- weekly maintenance scheduler (launchd) --"
./scripts/status_acceptance_weekly_launchd.sh || true

echo ""
echo "-- weekly maintenance scheduler (cron) --"
./scripts/status_acceptance_weekly_cron.sh || true

echo ""
echo "-- autonomous loop scheduler (launchd) --"
./scripts/status_autonomous_loop_launchd.sh || true

echo ""
echo "-- autonomous loop scheduler (cron) --"
./scripts/status_autonomous_loop_cron.sh || true

echo ""
echo "-- docker scheduler sidecar --"
if command -v docker >/dev/null 2>&1; then
  docker compose ps hive-scheduler 2>/dev/null || echo "hive-scheduler: unavailable"
else
  echo "docker: not found"
fi

if [[ "$TAIL_LINES" -gt 0 ]]; then
  echo ""
  echo "-- recent logs: acceptance-gate.out --"
  tail -n "$TAIL_LINES" .logs/acceptance-gate.out.log 2>/dev/null || echo "log missing: .logs/acceptance-gate.out.log"
  echo ""
  echo "-- recent logs: acceptance-gate.err --"
  tail -n "$TAIL_LINES" .logs/acceptance-gate.err.log 2>/dev/null || echo "log missing: .logs/acceptance-gate.err.log"
  echo ""
  echo "-- recent logs: acceptance-weekly.out --"
  tail -n "$TAIL_LINES" .logs/acceptance-weekly.out.log 2>/dev/null || echo "log missing: .logs/acceptance-weekly.out.log"
  echo ""
  echo "-- recent logs: acceptance-weekly.err --"
  tail -n "$TAIL_LINES" .logs/acceptance-weekly.err.log 2>/dev/null || echo "log missing: .logs/acceptance-weekly.err.log"
  echo ""
  echo "-- recent logs: acceptance-gate.cron --"
  tail -n "$TAIL_LINES" .logs/acceptance-gate.cron.log 2>/dev/null || echo "log missing: .logs/acceptance-gate.cron.log"
  echo ""
  echo "-- recent logs: acceptance-weekly.cron --"
  tail -n "$TAIL_LINES" .logs/acceptance-weekly.cron.log 2>/dev/null || echo "log missing: .logs/acceptance-weekly.cron.log"
  echo ""
  echo "-- recent logs: autonomous-loop.cron --"
  tail -n "$TAIL_LINES" .logs/autonomous-loop.cron.log 2>/dev/null || echo "log missing: .logs/autonomous-loop.cron.log"
  echo ""
  echo "-- recent logs: hive-scheduler (docker) --"
  if command -v docker >/dev/null 2>&1; then
    docker compose logs --tail="$TAIL_LINES" hive-scheduler 2>/dev/null || echo "hive-scheduler logs unavailable"
  else
    echo "docker: not found"
  fi
fi

echo ""
echo "[ok] acceptance scheduler snapshot completed"

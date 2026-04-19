#!/usr/bin/env bash

# Shared helpers for install/status/uninstall cron wrappers.

hive_cron_require_crontab() {
  if ! command -v crontab >/dev/null 2>&1; then
    echo "error: crontab is required" >&2
    return 1
  fi
}

hive_cron_has_crontab() {
  command -v crontab >/dev/null 2>&1
}

hive_cron_q() {
  printf "%q" "$1"
}

hive_cron_validate_expr() {
  local expr="$1"
  if [[ -z "$expr" ]]; then
    echo "error: cron expression must not be empty" >&2
    return 1
  fi
  if [[ "$expr" == *$'\n'* ]]; then
    echo "error: cron expression must be single-line" >&2
    return 1
  fi
  case "$expr" in
    @yearly|@annually|@monthly|@weekly|@daily|@hourly|@reboot)
      return 0
      ;;
  esac
  local fields
  fields="$(awk '{print NF}' <<<"$expr")"
  if [[ "$fields" -lt 5 ]]; then
    echo "error: cron expression must contain at least 5 fields or use @hourly-style macro" >&2
    return 1
  fi
}

hive_cron_current() {
  crontab -l 2>/dev/null || true
}

hive_cron_get_line() {
  local marker="$1"
  hive_cron_current | grep -F "# ${marker}" | tail -n 1 || true
}

hive_cron_upsert() {
  local marker="$1"
  local expr="$2"
  local command="$3"
  local tmp
  tmp="$(mktemp)"
  hive_cron_current | grep -F -v "# ${marker}" >"$tmp" || true
  printf "%s %s # %s\n" "$expr" "$command" "$marker" >>"$tmp"
  crontab "$tmp"
  rm -f "$tmp"
}

hive_cron_remove() {
  local marker="$1"
  local tmp
  tmp="$(mktemp)"
  hive_cron_current | grep -F -v "# ${marker}" >"$tmp" || true
  crontab "$tmp"
  rm -f "$tmp"
}

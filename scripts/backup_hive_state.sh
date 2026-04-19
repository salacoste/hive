#!/usr/bin/env bash
set -euo pipefail

NOW_UTC=$(date -u +"%Y%m%dT%H%M%SZ")
HIVE_HOME=${HIVE_HOME:-"$HOME/.hive"}
BACKUP_ROOT=${HIVE_BACKUP_ROOT:-"$HIVE_HOME/backups"}
BACKUP_DIR="$BACKUP_ROOT/$NOW_UTC"
ARCHIVE="$BACKUP_ROOT/hive-state-$NOW_UTC.tar.gz"

mkdir -p "$BACKUP_DIR"

copy_if_exists() {
  local src="$1"
  local dst_name="$2"
  if [[ -e "$src" ]]; then
    cp -a "$src" "$BACKUP_DIR/$dst_name"
  fi
}

copy_if_exists "$HIVE_HOME/credentials" "credentials"
copy_if_exists "$HIVE_HOME/server" "server"
copy_if_exists "$HIVE_HOME/configuration.json" "configuration.json"
copy_if_exists "$HIVE_HOME/secrets" "secrets"

if [[ -z "$(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)" ]]; then
  echo "No state files found under $HIVE_HOME; nothing to back up."
  rmdir "$BACKUP_DIR" || true
  exit 0
fi

# Normalize owner/perms in archive content at create time via tar options where supported.
# Fallback to plain tar if these options are unavailable.
if tar --help 2>/dev/null | grep -q -- '--owner'; then
  tar -czf "$ARCHIVE" \
    --owner=0 --group=0 --numeric-owner \
    -C "$BACKUP_DIR" .
else
  tar -czf "$ARCHIVE" -C "$BACKUP_DIR" .
fi

# Keep unpacked snapshot for quick local restore drills.
echo "Backup created: $ARCHIVE"
echo "Snapshot dir:  $BACKUP_DIR"

echo "To restore manually (example):"
echo "  tar -xzf '$ARCHIVE' -C '$HIVE_HOME'"

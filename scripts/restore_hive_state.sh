#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  restore_hive_state.sh --archive <path.tar.gz> [--dry-run] [--yes]
  restore_hive_state.sh --snapshot <dir>       [--dry-run] [--yes]

Options:
  --archive PATH   Path to backup tar.gz created by backup_hive_state.sh
  --snapshot DIR   Path to unpacked snapshot directory
  --dry-run        Show planned actions only
  --yes            Apply without interactive confirmation
EOF
}

ARCHIVE=""
SNAPSHOT=""
DRY_RUN=0
ASSUME_YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive)
      ARCHIVE=${2:-}
      shift 2
      ;;
    --snapshot)
      SNAPSHOT=${2:-}
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$ARCHIVE" && -z "$SNAPSHOT" ]]; then
  echo "Either --archive or --snapshot is required." >&2
  usage
  exit 2
fi
if [[ -n "$ARCHIVE" && -n "$SNAPSHOT" ]]; then
  echo "Use only one source: --archive or --snapshot." >&2
  exit 2
fi

HIVE_HOME=${HIVE_HOME:-"$HOME/.hive"}
TMPDIR_SRC=""
SOURCE_DIR=""
NOW_UTC=$(date -u +"%Y%m%dT%H%M%SZ")
PRE_BACKUP_DIR="$HIVE_HOME/pre-restore-$NOW_UTC"

cleanup() {
  if [[ -n "$TMPDIR_SRC" && -d "$TMPDIR_SRC" ]]; then
    rm -rf "$TMPDIR_SRC"
  fi
}
trap cleanup EXIT

if [[ -n "$ARCHIVE" ]]; then
  if [[ ! -f "$ARCHIVE" ]]; then
    echo "Archive not found: $ARCHIVE" >&2
    exit 2
  fi
  TMPDIR_SRC=$(mktemp -d)
  tar -xzf "$ARCHIVE" -C "$TMPDIR_SRC"
  SOURCE_DIR="$TMPDIR_SRC"
else
  if [[ ! -d "$SNAPSHOT" ]]; then
    echo "Snapshot directory not found: $SNAPSHOT" >&2
    exit 2
  fi
  SOURCE_DIR="$SNAPSHOT"
fi

ITEMS=(credentials server secrets configuration.json)

plan_copy() {
  local src="$1"
  local dst="$2"
  if [[ -e "$src" ]]; then
    echo "  restore: $src -> $dst"
  fi
}

echo "Restore plan (HIVE_HOME=$HIVE_HOME):"
for item in "${ITEMS[@]}"; do
  plan_copy "$SOURCE_DIR/$item" "$HIVE_HOME/$item"
done

echo "Pre-restore snapshot will be saved to: $PRE_BACKUP_DIR"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry-run mode: no changes applied."
  exit 0
fi

if [[ "$ASSUME_YES" -ne 1 ]]; then
  read -r -p "Proceed with restore? [y/N] " ans
  case "$ans" in
    y|Y|yes|YES) ;;
    *)
      echo "Restore cancelled."
      exit 0
      ;;
  esac
fi

mkdir -p "$PRE_BACKUP_DIR"
for item in "${ITEMS[@]}"; do
  if [[ -e "$HIVE_HOME/$item" ]]; then
    cp -a "$HIVE_HOME/$item" "$PRE_BACKUP_DIR/$item"
  fi
  if [[ -e "$SOURCE_DIR/$item" ]]; then
    rm -rf "$HIVE_HOME/$item"
    cp -a "$SOURCE_DIR/$item" "$HIVE_HOME/$item"
  fi
done

echo "Restore completed."
echo "Pre-restore snapshot: $PRE_BACKUP_DIR"

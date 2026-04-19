#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export HIVE_ACCEPTANCE_SELF_CHECK_RUN_PRESET_SMOKE=true
export HIVE_ACCEPTANCE_SELF_CHECK_RUN_RUNTIME_PARITY=true

exec ./scripts/acceptance_toolchain_self_check.sh "$@"

#!/usr/bin/env bash
set -euo pipefail

# Refresh GOOGLE_ACCESS_TOKEN from GOOGLE_REFRESH_TOKEN.
# Requires in .env:
#   GOOGLE_CLIENT_ID
#   GOOGLE_CLIENT_SECRET
#   GOOGLE_REFRESH_TOKEN
# Optional:
#   --recreate  Recreate hive-core after refresh (not needed for token-file mode)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RECREATE=0
if [[ "${1:-}" == "--recreate" ]]; then
  RECREATE=1
fi

uv run python scripts/google_oauth_token_manager.py refresh --workdir "$ROOT_DIR"

# Push token into runtime token file so Google tools pick it up without container restart.
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi
TOKEN_VALUE="${GOOGLE_ACCESS_TOKEN:-}"
TOKEN_FILE_PATH="${GOOGLE_ACCESS_TOKEN_FILE:-/data/storage/secrets/google_access_token}"
TOKEN_META_FILE_PATH="${GOOGLE_ACCESS_TOKEN_META_FILE:-${TOKEN_FILE_PATH}.meta.json}"
TOKEN_EXPIRES_AT_VALUE="${GOOGLE_TOKEN_EXPIRES_AT:-0}"
if [[ -n "$TOKEN_VALUE" ]]; then
  docker compose exec -u 0 -T hive-core sh -lc \
    "mkdir -p \"$(dirname "$TOKEN_FILE_PATH")\" \
      && printf '%s\n' '$TOKEN_VALUE' > '$TOKEN_FILE_PATH' \
      && printf '{\"expires_at\": %s, \"updated_at\": %s}\n' '$TOKEN_EXPIRES_AT_VALUE' '$(date +%s)' > '$TOKEN_META_FILE_PATH'" \
    >/dev/null 2>&1 || true
  echo "runtime token file updated: ${TOKEN_FILE_PATH}"
fi

if [[ "$RECREATE" -eq 1 ]]; then
  docker compose up -d --force-recreate hive-core >/dev/null
  echo "hive-core recreated to apply refreshed GOOGLE_ACCESS_TOKEN"
else
  echo "hive-core not recreated (default mode)"
fi

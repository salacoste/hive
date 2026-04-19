#!/usr/bin/env bash
# Docker entrypoint for Hive core service
set -e

# Create required directories
WORKSPACE_ROOT="${HIVE_WORKSPACE_ROOT:-/home/hiveuser/projects}"
mkdir -p /data/storage /data/credentials "${HOME}/.hive" /app/exports /app/examples "${WORKSPACE_ROOT}"
export AGENT_STORAGE_PATH=/data/storage

# Generate HIVE_CREDENTIAL_KEY if not set
if [ -z "${HIVE_CREDENTIAL_KEY:-}" ]; then
    export HIVE_CREDENTIAL_KEY=$(python3 -c "import base64,hashlib,os;print(base64.urlsafe_b64encode(hashlib.sha256(os.urandom(32)).digest()).decode())")
fi

# Write configuration.json if not present
CONFIG_FILE="${HOME}/.hive/configuration.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    python3 << 'PYEOF'
import json, os

config = {
    "llm": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-5-20250929",
        "max_tokens": 8192,
        "api_key_env_var": "ANTHROPIC_API_KEY"
    }
}

api_base = os.environ.get("ANTHROPIC_API_BASE", "")
if api_base:
    config["llm"]["api_base"] = api_base

zai_key = os.environ.get("ZAI_API_KEY", "")
if zai_key:
    config["worker_llm"] = {
        "provider": "openai",
        "model": "glm-5.1",
        "api_key_env_var": "ZAI_API_KEY",
        "api_base": "https://open.bigmodel.cn/api/paas/v4"
    }

# Ensure ~/.hive directory is writeable
os.makedirs(os.path.expanduser("~/.hive"), exist_ok=True)
with open(os.path.expanduser("~/.hive/configuration.json"), "w") as f:
    json.dump(config, f, indent=2)

print("Created ~/.hive/configuration.json")
PYEOF
fi

# Execute command
case "${1:-serve}" in
    serve|open)
        exec uv run hive serve --host 0.0.0.0 --port "${HIVE_CORE_PORT:-8787}" "${@:2}"
        ;;
    run|info|validate|list|shell|test-run|test-debug|test-list|test-stats|skill|mcp|debugger)
        exec uv run hive "$@"
        ;;
    *)
        exec "$@"
        ;;
esac

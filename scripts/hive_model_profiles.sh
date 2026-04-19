#!/usr/bin/env bash
set -euo pipefail

# Profile runner for Hive model selection.
# Usage:
#   scripts/hive_model_profiles.sh <profile> <hive args...>
#
# Profiles:
#   heavy         -> claude-opus-4-6, fallback gpt-5.4
#   implement     -> openai/gemini-3.1-pro-high, fallback openai/glm-5.1
#   docs          -> openai/glm-5.1
#   review        -> gpt-5.3-codex
#   validate      -> gpt-5.3-codex

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <profile> <hive args...>" >&2
  exit 2
fi

profile="$1"
shift

run_model() {
  local model="$1"
  shift
  uv run hive --model "$model" "$@"
}

case "$profile" in
  heavy)
    run_model "claude-opus-4-6" "$@" || run_model "gpt-5.4" "$@"
    ;;
  implement)
    run_model "openai/gemini-3.1-pro-high" "$@" || run_model "openai/glm-5.1" "$@"
    ;;
  docs)
    run_model "openai/glm-5.1" "$@"
    ;;
  review|validate)
    run_model "gpt-5.3-codex" "$@"
    ;;
  *)
    echo "Unknown profile: $profile" >&2
    echo "Expected one of: heavy, implement, docs, review, validate" >&2
    exit 2
    ;;
esac

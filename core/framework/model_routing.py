"""Model routing profiles and fallback chains.

Centralizes task-oriented model policy so CLI, server sessions, and runner
setup can resolve a consistent model chain without external wrapper scripts.
"""

from __future__ import annotations

from typing import Any

from framework.config import get_hive_config

# Built-in defaults requested for this workspace.
DEFAULT_MODEL_ROUTING: dict[str, list[str]] = {
    # Heavy/complex reasoning and solving.
    "heavy": ["claude-opus-4-6", "gpt-5.4"],
    # Implementation/execution path.
    # Use OpenAI-compatible routing in container-first deployments.
    "implementation": ["openai/gemini-3.1-pro-high", "openai/glm-5.1"],
    # Documentation writing.
    "documentation": ["openai/glm-5.1"],
    # Code review and validation.
    "review_validation": ["gpt-5.3-codex"],
}

# Command-to-profile defaults for native CLI integration.
DEFAULT_COMMAND_PROFILE: dict[str, str] = {
    "run": "implementation",
    "shell": "implementation",
    "validate": "review_validation",
    "serve": "heavy",
    "open": "heavy",
}


def _normalize_profile_name(name: str | None) -> str:
    if not name:
        return ""
    name = name.strip().lower()
    aliases = {
        "implement": "implementation",
        "impl": "implementation",
        "doc": "documentation",
        "docs": "documentation",
        "review": "review_validation",
        "validation": "review_validation",
    }
    return aliases.get(name, name)


def get_model_routing_map() -> dict[str, list[str]]:
    """Return effective model routing map from config, merged with defaults."""
    cfg = get_hive_config()
    raw = cfg.get("model_routing", {})
    merged: dict[str, list[str]] = {
        key: list(value) for key, value in DEFAULT_MODEL_ROUTING.items()
    }
    if isinstance(raw, dict):
        for k, v in raw.items():
            if not isinstance(k, str):
                continue
            nk = _normalize_profile_name(k)
            if isinstance(v, list):
                merged[nk] = [str(item).strip() for item in v if str(item).strip()]
    return merged


def resolve_profile_for_command(command: str, override: str | None = None) -> str | None:
    """Resolve profile by command name, optionally overridden by the caller."""
    if override:
        ov = _normalize_profile_name(override)
        return ov or None
    return DEFAULT_COMMAND_PROFILE.get(command)


def resolve_model_chain(
    *,
    explicit_model: str | None = None,
    profile: str | None = None,
    extra_fallback_models: list[str] | None = None,
) -> list[str]:
    """Return model chain (primary first), deduplicated and non-empty."""
    chain: list[str] = []
    if explicit_model:
        chain.append(explicit_model.strip())

    if profile:
        p = _normalize_profile_name(profile)
        routing = get_model_routing_map()
        chain.extend(routing.get(p, []))

    if extra_fallback_models:
        chain.extend([m.strip() for m in extra_fallback_models if m and m.strip()])

    # Deduplicate preserving order.
    out: list[str] = []
    seen: set[str] = set()
    for item in chain:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def resolve_model_connection(
    model: str,
    cfg: dict[str, Any] | None = None,
) -> dict[str, str | None]:
    """Infer api key env + api_base for a model from env conventions and config.

    The returned shape is:
      {"api_key_env_var": "...", "api_base_env_var": "...", "api_base": "..."}
    """
    model_l = model.lower()
    cfg = cfg or get_hive_config()
    llm_cfg = cfg.get("llm", {}) if isinstance(cfg, dict) else {}

    # Defaults from global llm config for the primary model.
    default_api_base = llm_cfg.get("api_base") if isinstance(llm_cfg, dict) else None

    if model_l.startswith("anthropic/") or model_l.startswith("claude"):
        return {
            "api_key_env_var": "ANTHROPIC_API_KEY",
            "api_base_env_var": "ANTHROPIC_API_BASE",
            "api_base": default_api_base if llm_cfg.get("provider") == "anthropic" else None,
        }
    if model_l.startswith("gemini/") or model_l.startswith("google/"):
        return {
            "api_key_env_var": "GEMINI_API_KEY",
            "api_base_env_var": "GEMINI_API_BASE",
            "api_base": None,
        }
    if model_l.startswith("glm-") or model_l.startswith("z-ai/") or model_l.startswith("zai-glm"):
        return {
            "api_key_env_var": "ZAI_API_KEY",
            "api_base_env_var": "ZAI_API_BASE",
            "api_base": None,
        }
    if model_l.startswith("openrouter/"):
        return {
            "api_key_env_var": "OPENROUTER_API_KEY",
            "api_base_env_var": None,
            "api_base": "https://openrouter.ai/api/v1",
        }
    if model_l.startswith(("gpt-", "openai/", "gpt-5.3-codex", "gpt-5.4")):
        return {
            "api_key_env_var": "OPENAI_API_KEY",
            "api_base_env_var": "OPENAI_API_BASE",
            "api_base": None,
        }
    return {
        "api_key_env_var": llm_cfg.get("api_key_env_var") if isinstance(llm_cfg, dict) else None,
        "api_base_env_var": None,
        "api_base": default_api_base,
    }

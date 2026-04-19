#!/usr/bin/env python3
"""Audit MCP credential environment variables for this repo.

Usage:
  uv run python scripts/audit_mcp_credentials.py
  uv run python scripts/audit_mcp_credentials.py --priority
  uv run python scripts/audit_mcp_credentials.py --tools web_search github_create_issue
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import dotenv_values

from aden_tools.credentials import CREDENTIAL_SPECS


PRIORITY_VARS = [
    "BRAVE_SEARCH_API_KEY",
    "EXA_API_KEY",
    "SERPAPI_API_KEY",
    "GITHUB_TOKEN",
    "SLACK_BOT_TOKEN",
    "NOTION_API_TOKEN",
    "GOOGLE_API_KEY",
    "GOOGLE_CSE_ID",
    "RESEND_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "DISCORD_BOT_TOKEN",
    "DATABASE_URL",
    "REDIS_URL",
]

BUNDLES: dict[str, dict[str, list[str]]] = {
    # Requested operating stack: web search + scrape + telegram + github + google workspace.
    "local_pro_stack": {
        "required": [
            "BRAVE_SEARCH_API_KEY",
            "GITHUB_TOKEN",
            "TELEGRAM_BOT_TOKEN",
            "GOOGLE_ACCESS_TOKEN",
            "REDIS_URL",
            "DATABASE_URL",
        ],
        # Optional integrations for extended Google MCP capability.
        "optional": [
            "GOOGLE_MAPS_API_KEY",
            "GOOGLE_SEARCH_CONSOLE_TOKEN",
            "GOOGLE_APPLICATION_CREDENTIALS",
        ],
    },
}


def _build_tool_to_env() -> dict[str, set[str]]:
    tool_to_env: dict[str, set[str]] = {}
    for spec in CREDENTIAL_SPECS.values():
        for tool_name in spec.tools:
            tool_to_env.setdefault(tool_name, set()).add(spec.env_var)
    return tool_to_env


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values = dotenv_values(path)
    return {k: v for k, v in values.items() if isinstance(v, str)}


def _is_set(var_name: str, dotenv_map: dict[str, str]) -> bool:
    env_value = os.environ.get(var_name)
    if env_value:
        return True
    return bool(dotenv_map.get(var_name))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit MCP credential keys")
    parser.add_argument(
        "--dotenv",
        default=".env",
        help="Path to .env file (default: .env)",
    )
    parser.add_argument(
        "--priority",
        action="store_true",
        help="Show only priority integration keys",
    )
    parser.add_argument(
        "--tools",
        nargs="*",
        default=[],
        help="Filter by tool names and show only required env vars for those tools",
    )
    parser.add_argument(
        "--bundle",
        type=str,
        default=None,
        choices=sorted(BUNDLES.keys()),
        help="Audit a predefined bundle of env vars",
    )
    args = parser.parse_args()

    dotenv_map = _load_dotenv(Path(args.dotenv))
    tool_to_env = _build_tool_to_env()

    if args.tools:
        target_vars: set[str] = set()
        for tool in args.tools:
            target_vars.update(tool_to_env.get(tool, set()))
        var_list = sorted(target_vars)
        optional_list: list[str] = []
    elif args.bundle:
        bundle = BUNDLES[args.bundle]
        var_list = sorted(bundle.get("required", []))
        optional_list = sorted(bundle.get("optional", []))
    elif args.priority:
        var_list = sorted(PRIORITY_VARS)
        optional_list = []
    else:
        var_list = sorted({spec.env_var for spec in CREDENTIAL_SPECS.values() if spec.env_var})
        optional_list = []

    set_vars = [v for v in var_list if _is_set(v, dotenv_map)]
    missing_vars = [v for v in var_list if v not in set_vars]
    optional_set = [v for v in optional_list if _is_set(v, dotenv_map)]
    optional_missing = [v for v in optional_list if v not in optional_set]

    print(f"Checked vars: {len(var_list)}")
    print(f"Set: {len(set_vars)}")
    print(f"Missing: {len(missing_vars)}")
    if optional_list:
        print(f"Optional checked: {len(optional_list)}")
        print(f"Optional set: {len(optional_set)}")
        print(f"Optional missing: {len(optional_missing)}")
    print()

    if set_vars:
        print("Set:")
        for name in set_vars:
            print(f"  - {name}")
        print()

    if missing_vars:
        print("Missing:")
        for name in missing_vars:
            print(f"  - {name}")
        print()
        print("Next step: add missing keys to .env (docker compose loads them via env_file).")
    elif optional_missing:
        print("Optional missing (non-blocking):")
        for name in optional_missing:
            print(f"  - {name}")
        print()
        print("Optional integrations can be configured later without blocking local_pro_stack.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Export Hive MCP tool inventory and credential mappings.

Usage:
  uv run python scripts/export_mcp_inventory.py
  uv run python scripts/export_mcp_inventory.py --out-dir docs/ops
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fastmcp import FastMCP

from aden_tools.credentials import CREDENTIAL_SPECS, CredentialStoreAdapter
from aden_tools.tools import register_all_tools


def _collect_tools(include_unverified: bool) -> list[str]:
    mcp = FastMCP("tools")
    creds = CredentialStoreAdapter.default()
    tools = register_all_tools(mcp, credentials=creds, include_unverified=include_unverified)
    return sorted(set(tools))


def _build_tool_env_map() -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for spec in CREDENTIAL_SPECS.values():
        for tool_name in spec.tools:
            mapping.setdefault(tool_name, set()).add(spec.env_var)
    return mapping


def _write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export MCP inventory for Hive")
    parser.add_argument("--out-dir", default="docs/ops", help="Output directory (default: docs/ops)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)

    verified = _collect_tools(include_unverified=False)
    all_tools = _collect_tools(include_unverified=True)
    tool_env = _build_tool_env_map()

    verified_file = out_dir / "mcp-tools-verified.txt"
    all_file = out_dir / "mcp-tools-all.txt"
    envs_file = out_dir / "mcp-env-vars-all.txt"
    map_file = out_dir / "mcp-tool-env-map.csv"

    _write_lines(verified_file, [f"# verified tools: {len(verified)}", *verified])
    _write_lines(all_file, [f"# all tools (include_unverified=true): {len(all_tools)}", *all_tools])

    all_envs = sorted({spec.env_var for spec in CREDENTIAL_SPECS.values() if spec.env_var})
    _write_lines(envs_file, [f"# env vars from credential specs: {len(all_envs)}", *all_envs])

    csv_lines = ["tool_name,env_vars"]
    for tool in sorted(all_tools):
        envs = sorted(tool_env.get(tool, set()))
        csv_lines.append(f"{tool},{'|'.join(envs)}")
    _write_lines(map_file, csv_lines)

    print(f"Wrote {verified_file} ({len(verified)} tools)")
    print(f"Wrote {all_file} ({len(all_tools)} tools)")
    print(f"Wrote {envs_file} ({len(all_envs)} env vars)")
    print(f"Wrote {map_file} ({len(all_tools)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

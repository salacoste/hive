#!/usr/bin/env python3
"""Smoke-test Google MCP tools using current env credentials.

Checks:
- calendar_list_events
- gmail_list_messages
- google_docs_create_document (optional write)
- google_sheets_create_spreadsheet (optional write)
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from fastmcp import FastMCP

from aden_tools.tools.calendar_tool import register_tools as register_calendar_tools
from aden_tools.tools.gmail_tool import register_tools as register_gmail_tools
from aden_tools.tools.google_docs_tool import register_tools as register_google_docs_tools
from aden_tools.tools.google_sheets_tool import register_tools as register_google_sheets_tools


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _tool_fn(mcp: FastMCP, name: str) -> Callable[..., dict[str, Any]]:
    manager = getattr(mcp, "_tool_manager", None)
    if manager is None or not hasattr(manager, "_tools"):
        raise RuntimeError("FastMCP tool manager unavailable")
    entry = manager._tools.get(name)
    if entry is None:
        raise RuntimeError(f"Tool not registered: {name}")
    return entry.fn


def _ok_result(name: str, response: dict[str, Any]) -> dict[str, Any]:
    return {"tool": name, "ok": True, "response": response}


def _err_result(name: str, response: dict[str, Any]) -> dict[str, Any]:
    return {"tool": name, "ok": False, "error": response.get("error", "unknown error"), "response": response}


def main() -> int:
    parser = argparse.ArgumentParser(description="Google MCP smoke test")
    parser.add_argument("--dotenv", default=".env", help="Path to .env")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Also run write checks (create doc + create spreadsheet)",
    )
    args = parser.parse_args()

    _load_env(Path(args.dotenv))

    mcp = FastMCP("google-smoke")
    register_calendar_tools(mcp, credentials=None)
    register_gmail_tools(mcp, credentials=None)
    register_google_docs_tools(mcp, credentials=None)
    register_google_sheets_tools(mcp, credentials=None)

    checks: list[dict[str, Any]] = []

    calendar_list_events = _tool_fn(mcp, "calendar_list_events")
    gmail_list_messages = _tool_fn(mcp, "gmail_list_messages")
    google_docs_create_document = _tool_fn(mcp, "google_docs_create_document")
    google_sheets_create_spreadsheet = _tool_fn(mcp, "google_sheets_create_spreadsheet")

    cal_resp = calendar_list_events(max_results=3)
    checks.append(
        _err_result("calendar_list_events", cal_resp)
        if isinstance(cal_resp, dict) and cal_resp.get("error")
        else _ok_result("calendar_list_events", cal_resp if isinstance(cal_resp, dict) else {"raw": str(cal_resp)})
    )

    gmail_resp = gmail_list_messages(max_results=5)
    checks.append(
        _err_result("gmail_list_messages", gmail_resp)
        if isinstance(gmail_resp, dict) and gmail_resp.get("error")
        else _ok_result("gmail_list_messages", gmail_resp if isinstance(gmail_resp, dict) else {"raw": str(gmail_resp)})
    )

    if args.write:
        ts = int(time.time())
        doc_resp = google_docs_create_document(title=f"Hive Smoke Doc {ts}")
        checks.append(
            _err_result("google_docs_create_document", doc_resp)
            if isinstance(doc_resp, dict) and doc_resp.get("error")
            else _ok_result("google_docs_create_document", doc_resp if isinstance(doc_resp, dict) else {"raw": str(doc_resp)})
        )

        sheet_resp = google_sheets_create_spreadsheet(
            title=f"Hive Smoke Sheet {ts}",
            sheet_titles=["Smoke"],
        )
        checks.append(
            _err_result("google_sheets_create_spreadsheet", sheet_resp)
            if isinstance(sheet_resp, dict) and sheet_resp.get("error")
            else _ok_result("google_sheets_create_spreadsheet", sheet_resp if isinstance(sheet_resp, dict) else {"raw": str(sheet_resp)})
        )

    failed = [c for c in checks if not c.get("ok")]
    print(json.dumps({"checks": checks, "failed": len(failed)}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

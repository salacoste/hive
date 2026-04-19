#!/usr/bin/env python3
"""Build a focused overlap patch for Batch A activation hotspots."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TARGET_REF = os.environ.get("HIVE_UPSTREAM_TARGET_REF", "origin/main")
OUT_DIR = Path("docs/ops/upstream-migration")
PATCH_PATH = OUT_DIR / "overlap-batch-a-focus-latest.patch"
SUMMARY_PATH = OUT_DIR / "overlap-batch-a-focus-summary-latest.md"

FILES = [
    "core/framework/server/app.py",
    "core/framework/server/routes_execution.py",
    "core/framework/server/routes_sessions.py",
    "core/framework/server/queen_orchestrator.py",
    "core/framework/server/routes_credentials.py",
    "core/framework/server/session_manager.py",
]

KEYWORDS = [
    "from typing import Any",
    "def create_app(model: str | None = None, model_profile: str | None = None)",
    "model_profile=model_profile",
    "APP_KEY_MANAGER",
    "APP_KEY_CREDENTIAL_STORE",
    "APP_KEY_TELEGRAM_BRIDGE",
    "register_autonomous_routes",
    "register_project_routes",
    "/api/telegram/bridge/status",
    "APP_KEY_PROJECT_EXEC_",
    "/api/projects/{project_id}/queue",
    'project_id = body.get("project_id")',
    "manager.list_sessions(project_id=project_id)",
    "/api/agents",
    "/api/sessions/{session_id}/reveal",
    "/api/sessions/{session_id}/graph",
    "_project_workspace_from_metadata",
    "session.project_id",
    "APP_KEY_AUTONOMOUS_STORE",
]


@dataclass
class Hunk:
    header: str
    lines: list[str]

    def matches(self) -> bool:
        for line in self.lines:
            for kw in KEYWORDS:
                if kw in line:
                    return True
        return False

    def new_start_line(self) -> int:
        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", self.header.strip())
        if not m:
            return 10**9
        return int(m.group(1))

    def render(self) -> str:
        return self.header + "".join(self.lines)


@dataclass
class FileSection:
    file_header: str
    pre_hunk_lines: list[str]
    hunks: list[Hunk]

    def matched_hunks(self) -> list[Hunk]:
        matched = [h for h in self.hunks if h.matches()]
        if not matched:
            return []
        # Keep early bootstrap/import hunks for selected files to avoid
        # introducing symbol references without their import/type definitions.
        extra = [h for h in self.hunks if h.new_start_line() <= 120]
        merged: list[Hunk] = []
        seen: set[int] = set()
        for h in matched + extra:
            key = id(h)
            if key in seen:
                continue
            seen.add(key)
            merged.append(h)
        return merged

    def render(self) -> str:
        matched = self.matched_hunks()
        if not matched:
            return ""
        return self.file_header + "".join(self.pre_hunk_lines) + "".join(h.render() for h in matched)


def _load_diff() -> str:
    result = subprocess.run(
        ["git", "diff", "--no-color", TARGET_REF, "--", *FILES],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    return result.stdout


def _parse_sections(diff_text: str) -> list[FileSection]:
    lines = diff_text.splitlines(keepends=True)
    sections: list[FileSection] = []

    current_header = ""
    current_pre: list[str] = []
    current_hunks: list[Hunk] = []
    current_hunk_header = ""
    current_hunk_lines: list[str] = []
    in_hunk = False

    def finalize_hunk() -> None:
        nonlocal current_hunk_header, current_hunk_lines, in_hunk
        if in_hunk and current_hunk_header:
            current_hunks.append(Hunk(header=current_hunk_header, lines=list(current_hunk_lines)))
        current_hunk_header = ""
        current_hunk_lines = []
        in_hunk = False

    def finalize_section() -> None:
        nonlocal current_header, current_pre, current_hunks
        finalize_hunk()
        if current_header:
            sections.append(
                FileSection(
                    file_header=current_header,
                    pre_hunk_lines=list(current_pre),
                    hunks=list(current_hunks),
                )
            )
        current_header = ""
        current_pre = []
        current_hunks = []

    for line in lines:
        if line.startswith("diff --git "):
            finalize_section()
            current_header = line
            continue

        if not current_header:
            continue

        if line.startswith("@@ "):
            finalize_hunk()
            current_hunk_header = line
            current_hunk_lines = []
            in_hunk = True
            continue

        if in_hunk:
            current_hunk_lines.append(line)
        else:
            current_pre.append(line)

    finalize_section()
    return sections


def _write_outputs(sections: list[FileSection]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rendered = "".join(section.render() for section in sections)
    PATCH_PATH.write_text(rendered, encoding="utf-8")

    matched_files = 0
    matched_hunks = 0
    matched_file_paths: list[str] = []
    for section in sections:
        m = section.matched_hunks()
        if m:
            matched_files += 1
            matched_hunks += len(m)
            path = ""
            for line in section.pre_hunk_lines:
                if line.startswith("+++ b/"):
                    path = line.removeprefix("+++ b/").strip()
                    break
            if path:
                matched_file_paths.append(path)

    summary = [
        "# Overlap Batch A Focus Patch Summary",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Target ref: `{TARGET_REF}`",
        f"- Focus patch: `{PATCH_PATH}`",
        f"- Matched files: {matched_files}",
        f"- Matched hunks: {matched_hunks}",
        "",
        "## Keywords",
        "",
    ]
    summary.extend([f"- `{kw}`" for kw in KEYWORDS])
    summary.extend(["", "## Matched Files", ""])
    if matched_file_paths:
        summary.extend([f"- `{p}`" for p in matched_file_paths])
    else:
        summary.append("- none")
    summary.append("")
    SUMMARY_PATH.write_text("\n".join(summary), encoding="utf-8")


def main() -> int:
    try:
        diff = _load_diff()
        sections = _parse_sections(diff)
        _write_outputs(sections)
    except Exception as exc:
        print(f"[fail] {exc}")
        return 1
    print(f"[ok] wrote {PATCH_PATH}")
    print(f"[ok] wrote {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

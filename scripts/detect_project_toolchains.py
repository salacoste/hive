#!/usr/bin/env python3
"""Detect project toolchains and emit Docker build-arg profile recommendations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

TOOLCHAIN_MARKERS: dict[str, tuple[str, ...]] = {
    "node": (
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "bun.lockb",
        "tsconfig.json",
    ),
    "python": (
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "setup.cfg",
        "poetry.lock",
        "uv.lock",
    ),
    "go": ("go.mod", "go.work"),
    "rust": ("Cargo.toml", "Cargo.lock"),
    "jvm": (
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "gradlew",
        "mvnw",
    ),
}

DOCKER_BUILD_ARGS: dict[str, str] = {
    "node": "HIVE_DOCKER_INSTALL_NODE",
    "go": "HIVE_DOCKER_INSTALL_GO",
    "rust": "HIVE_DOCKER_INSTALL_RUST",
    "jvm": "HIVE_DOCKER_INSTALL_JAVA",
}

STACK_PRIORITY: tuple[str, ...] = ("node", "python", "go", "rust", "jvm")

_URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_HOST_PATH_RE = re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}/.+$")


@dataclass
class DetectionResult:
    workspace: str
    repository: str
    toolchains: list[str]
    marker_hits: dict[str, list[str]]
    docker_build_args: dict[str, int]
    recommended_stack: str
    plan_fingerprint: str
    confirm_token: str


def _find_markers(root: Path, marker: str) -> list[str]:
    matches: list[str] = []
    if marker.startswith("**/"):
        pattern = marker[3:]
        for p in root.rglob(pattern):
            if p.is_file():
                matches.append(str(p.relative_to(root)))
        return matches

    direct = root / marker
    if direct.exists():
        matches.append(marker)
    return matches


def _recommend_stack(found: list[str]) -> str:
    found_set = set(found)
    if "node" in found_set and "python" in found_set:
        return "fullstack"
    for stack in STACK_PRIORITY:
        if stack in found_set:
            return stack
    return "node"


def _plan_fingerprint(
    *,
    repository: str,
    toolchains: list[str],
    marker_hits: dict[str, list[str]],
    docker_build_args: dict[str, int],
    recommended_stack: str,
) -> str:
    """Stable plan fingerprint used for explicit human approval tokens.

    Do not include local absolute workspace paths: repository-based detection
    uses a temporary clone path and must still produce deterministic output.
    """
    payload = {
        "repository": repository,
        "toolchains": toolchains,
        "marker_hits": {k: sorted(v) for k, v in sorted(marker_hits.items())},
        "docker_build_args": {k: int(v) for k, v in sorted(docker_build_args.items())},
        "recommended_stack": recommended_stack,
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()[:8].upper()


def _confirm_token(build_args: dict[str, int], *, plan_fingerprint: str) -> str:
    enabled: list[str] = []
    for stack in ("node", "go", "rust", "jvm"):
        var = DOCKER_BUILD_ARGS[stack]
        if build_args.get(var, 0) == 1:
            enabled.append(stack.upper())
    suffix = "_".join(enabled) if enabled else "BASE"
    return f"APPLY_{suffix}_{plan_fingerprint}"


def _normalize_repository_clone_url(url: str) -> str:
    """Normalize shorthand host/path repository strings for git clone.

    Example: ``github.com/acme/repo`` -> ``https://github.com/acme/repo``.
    """
    value = (url or "").strip()
    if not value:
        return value
    if _URL_SCHEME_RE.match(value):
        return value
    if value.startswith(("git@", "ssh://", "file://", "/", "./", "../", "~")):
        return value
    if _HOST_PATH_RE.match(value):
        return f"https://{value}"
    return value


def detect_toolchains(root: Path, *, repository: str = "") -> DetectionResult:
    marker_hits: dict[str, list[str]] = {}
    for toolchain, markers in TOOLCHAIN_MARKERS.items():
        hits: list[str] = []
        for marker in markers:
            hits.extend(_find_markers(root, marker))
        if hits:
            marker_hits[toolchain] = sorted(set(hits))

    toolchains = [name for name in STACK_PRIORITY if name in marker_hits]
    build_args: dict[str, int] = {}
    for var in DOCKER_BUILD_ARGS.values():
        build_args[var] = 0
    for stack, var in DOCKER_BUILD_ARGS.items():
        if stack in toolchains:
            build_args[var] = 1

    stack = _recommend_stack(toolchains)
    fingerprint = _plan_fingerprint(
        repository=repository,
        toolchains=toolchains,
        marker_hits=marker_hits,
        docker_build_args=build_args,
        recommended_stack=stack,
    )
    token = _confirm_token(build_args, plan_fingerprint=fingerprint)
    return DetectionResult(
        workspace=str(root),
        repository=repository,
        toolchains=toolchains,
        marker_hits=marker_hits,
        docker_build_args=build_args,
        recommended_stack=stack,
        plan_fingerprint=fingerprint,
        confirm_token=token,
    )


def _clone_repo(url: str) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
    normalized_url = _normalize_repository_clone_url(url)
    tmp_dir = tempfile.TemporaryDirectory(prefix="hive-toolchain-detect-")
    dst = Path(tmp_dir.name) / "repo"
    proc = subprocess.run(
        ["git", "clone", "--depth", "1", normalized_url, str(dst)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        tmp_dir.cleanup()
        err = (proc.stderr or proc.stdout or "git clone failed").strip()
        raise RuntimeError(f"cannot clone repository: {err}")
    return dst, tmp_dir


def _render_human(result: DetectionResult) -> str:
    lines: list[str] = []
    lines.append(f"workspace: {result.workspace}")
    if result.repository:
        lines.append(f"repository: {result.repository}")
    lines.append(f"detected_toolchains: {', '.join(result.toolchains) if result.toolchains else 'none'}")
    lines.append(f"recommended_stack: {result.recommended_stack}")
    lines.append(f"plan_fingerprint: {result.plan_fingerprint}")
    lines.append("docker_build_args:")
    for key in sorted(result.docker_build_args):
        lines.append(f"  {key}={result.docker_build_args[key]}")
    lines.append(f"confirm_token: {result.confirm_token}")
    if result.marker_hits:
        lines.append("marker_hits:")
        for toolchain in sorted(result.marker_hits):
            lines.append(f"  {toolchain}:")
            for marker in result.marker_hits[toolchain]:
                lines.append(f"    - {marker}")
    return "\n".join(lines)


def _render_env(result: DetectionResult) -> str:
    lines: list[str] = []
    for key in sorted(result.docker_build_args):
        lines.append(f"{key}={result.docker_build_args[key]}")
    lines.append(f"HIVE_ONBOARDING_STACK={result.recommended_stack}")
    lines.append(f"HIVE_TOOLCHAIN_PLAN_FINGERPRINT={result.plan_fingerprint}")
    lines.append(f"HIVE_TOOLCHAIN_CONFIRM_TOKEN={result.confirm_token}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect project toolchains and recommend Hive Docker build args."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--workspace", type=str, help="Local workspace path")
    src.add_argument("--repository", type=str, help="Git repository URL to clone and inspect")
    parser.add_argument(
        "--format",
        choices=("human", "json", "env"),
        default="human",
        help="Output format",
    )
    args = parser.parse_args(argv)

    temp_clone: tempfile.TemporaryDirectory[str] | None = None
    try:
        if args.workspace:
            root = Path(args.workspace).expanduser().resolve()
            if not root.exists():
                print(f"[fail] workspace not found: {root}")
                return 2
        else:
            try:
                root, temp_clone = _clone_repo(args.repository)
            except RuntimeError as e:
                print(f"[fail] {e}")
                return 2

        result = detect_toolchains(root, repository=args.repository or "")
        if args.format == "json":
            print(json.dumps(result.__dict__, ensure_ascii=True, indent=2))
        elif args.format == "env":
            print(_render_env(result))
        else:
            print(_render_human(result))
        return 0
    finally:
        if temp_clone is not None:
            temp_clone.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

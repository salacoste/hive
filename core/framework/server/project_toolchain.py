"""Project toolchain planning helpers (plan -> approve -> apply contract)."""

from __future__ import annotations

import importlib.util
import shlex
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DETECT_SCRIPT_PATH = REPO_ROOT / "scripts" / "detect_project_toolchains.py"
APPLY_SCRIPT_PATH = REPO_ROOT / "scripts" / "apply_hive_toolchain_profile.sh"


def _load_detector_module():
    if not DETECT_SCRIPT_PATH.exists():
        raise RuntimeError(f"toolchain detector script not found: {DETECT_SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location(
        "hive_detect_project_toolchains_runtime",
        DETECT_SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load toolchain detector module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def resolve_toolchain_source(project: dict[str, Any], body: dict[str, Any]) -> dict[str, str | None]:
    workspace_path = str(body.get("workspace_path") or "").strip() or None
    explicit_repository = str(body.get("repository") or "").strip() or None
    repository = explicit_repository
    if not workspace_path and not repository:
        repository = str(project.get("repository") or "").strip() or None
    if workspace_path and explicit_repository:
        raise ValueError("provide only one source: workspace_path or repository")
    if not workspace_path and not repository:
        raise ValueError("workspace_path or repository is required")
    return {
        "workspace_path": workspace_path,
        "repository": repository,
    }


def detect_toolchain_plan(
    *,
    workspace_path: str | None,
    repository: str | None,
) -> dict[str, Any]:
    detector = _load_detector_module()
    temp_clone: tempfile.TemporaryDirectory[str] | None = None
    try:
        if workspace_path:
            root = Path(workspace_path).expanduser().resolve()
            if not root.exists():
                raise ValueError(f"workspace not found: {root}")
            result = detector.detect_toolchains(root, repository="")
        else:
            assert repository
            root, temp_clone = detector._clone_repo(repository)
            result = detector.detect_toolchains(root, repository=repository)
        payload = dict(result.__dict__)
    finally:
        if temp_clone is not None:
            temp_clone.cleanup()

    return {
        "workspace": str(payload.get("workspace") or ""),
        "repository": str(payload.get("repository") or ""),
        "toolchains": list(payload.get("toolchains") or []),
        "marker_hits": dict(payload.get("marker_hits") or {}),
        "docker_build_args": dict(payload.get("docker_build_args") or {}),
        "recommended_stack": str(payload.get("recommended_stack") or "node"),
        "plan_fingerprint": str(payload.get("plan_fingerprint") or ""),
        "confirm_token": str(payload.get("confirm_token") or ""),
        "generated_at": time.time(),
    }


def build_apply_commands(
    *,
    workspace_path: str | None,
    repository: str | None,
    confirm_token: str,
) -> dict[str, str]:
    apply_script = str(APPLY_SCRIPT_PATH)
    if workspace_path:
        src_flags = f"--workspace {shlex.quote(workspace_path)}"
    else:
        src_flags = f"--repository {shlex.quote(str(repository or ''))}"
    preview = f"{shlex.quote(apply_script)} {src_flags}"
    apply = f"{shlex.quote(apply_script)} {src_flags} --apply --confirm {shlex.quote(confirm_token)}"
    return {
        "preview_command": preview,
        "apply_command": apply,
    }


def build_env_exports(plan: dict[str, Any]) -> list[str]:
    args = plan.get("docker_build_args")
    if not isinstance(args, dict):
        return []
    lines: list[str] = []
    for key in sorted(args):
        lines.append(f"export {key}={int(args[key])}")
    return lines

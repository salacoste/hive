"""Project onboarding helpers for repository bootstrap and dry-run checks."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

STACKS = {"node", "python", "go", "jvm", "rust", "fullstack"}
REPO_TYPES = {"single", "monorepo"}


def _required_binaries(stack: str) -> tuple[str, ...]:
    if stack == "python":
        return ("uv",)
    if stack in {"node", "fullstack"}:
        return ("node", "npm")
    if stack == "go":
        return ("go",)
    if stack == "rust":
        return ("rustc", "cargo")
    if stack == "jvm":
        return ("java",)
    return ()


def _default_commands(stack: str) -> dict[str, str]:
    if stack == "python":
        return {
            "install": "uv sync",
            "lint": "uv run ruff check .",
            "typecheck": "uv run mypy .",
            "test": "uv run pytest",
            "build": "echo \"no build step\"",
            "smoke": "echo \"smoke ok\"",
        }
    if stack == "go":
        return {
            "install": "go mod download",
            "lint": "go vet ./...",
            "typecheck": "echo \"go has compile-time type checks\"",
            "test": "go test ./...",
            "build": "go build ./...",
            "smoke": "echo \"smoke ok\"",
        }
    if stack == "rust":
        return {
            "install": "cargo fetch",
            "lint": "cargo fmt --all -- --check",
            "typecheck": "cargo check --all-targets",
            "test": "cargo test",
            "build": "cargo build --release",
            "smoke": "cargo test -q",
        }
    if stack == "jvm":
        return {
            "install": (
                "if [ -f ./gradlew ]; then ./gradlew --no-daemon dependencies; "
                "elif command -v gradle >/dev/null 2>&1; then gradle dependencies; "
                "elif command -v mvn >/dev/null 2>&1; then mvn -q -DskipTests dependency:go-offline; "
                "else echo \"gradle or mvn is required\" && exit 1; fi"
            ),
            "lint": (
                "if [ -f ./gradlew ]; then ./gradlew --no-daemon check -x test; "
                "elif command -v gradle >/dev/null 2>&1; then gradle check -x test; "
                "elif command -v mvn >/dev/null 2>&1; then mvn -q -DskipTests verify; "
                "else echo \"gradle or mvn is required\" && exit 1; fi"
            ),
            "typecheck": (
                "if [ -f ./gradlew ]; then ./gradlew --no-daemon classes; "
                "elif command -v gradle >/dev/null 2>&1; then gradle classes; "
                "elif command -v mvn >/dev/null 2>&1; then mvn -q -DskipTests compile; "
                "else echo \"gradle or mvn is required\" && exit 1; fi"
            ),
            "test": (
                "if [ -f ./gradlew ]; then ./gradlew --no-daemon test; "
                "elif command -v gradle >/dev/null 2>&1; then gradle test; "
                "elif command -v mvn >/dev/null 2>&1; then mvn test; "
                "else echo \"gradle or mvn is required\" && exit 1; fi"
            ),
            "build": (
                "if [ -f ./gradlew ]; then ./gradlew --no-daemon build -x test; "
                "elif command -v gradle >/dev/null 2>&1; then gradle build -x test; "
                "elif command -v mvn >/dev/null 2>&1; then mvn -q -DskipTests package; "
                "else echo \"gradle or mvn is required\" && exit 1; fi"
            ),
            "smoke": "echo \"smoke ok\"",
        }
    return {
        "install": "if [ -f package-lock.json ]; then npm ci; else npm install; fi",
        "lint": "npm run lint",
        "typecheck": "npm run typecheck",
        "test": "npm test -- --runInBand",
        "build": "npm run build",
        "smoke": "npm run smoke",
    }


def _yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _manifest_template(
    *,
    repo_name: str,
    stack: str,
    repo_type: str,
    commands: dict[str, str],
    required_checks: list[str],
) -> str:
    checks = required_checks or ["lint", "test", "build"]
    checks_yaml = "\n".join(f"    - {_yaml_quote(c)}" for c in checks)
    return "\n".join(
        [
            'schema_version: "1.0"',
            "",
            "repository:",
            f"  name: {_yaml_quote(repo_name)}",
            f"  stack: {_yaml_quote(stack)}",
            f"  repo_type: {_yaml_quote(repo_type)}",
            "",
            "workspace:",
            '  default_workdir: "."',
            "  workdirs:",
            '    - "."',
            "",
            "automation:",
            f"  install:\n    - {_yaml_quote(commands['install'])}",
            f"  lint:\n    - {_yaml_quote(commands['lint'])}",
            f"  typecheck:\n    - {_yaml_quote(commands['typecheck'])}",
            f"  test:\n    - {_yaml_quote(commands['test'])}",
            f"  build:\n    - {_yaml_quote(commands['build'])}",
            f"  smoke:\n    - {_yaml_quote(commands['smoke'])}",
            "",
            "execution:",
            "  default_flow:",
            '    - stage: "design"',
            '      mode: "queen_plan"',
            '      model_profile: "strategy_heavy"',
            '    - stage: "implement"',
            '      mode: "worker_execute"',
            '      model_profile: "implementation"',
            '    - stage: "review"',
            '      mode: "worker_review"',
            '      model_profile: "review_validation"',
            '    - stage: "validate"',
            '      mode: "worker_validate"',
            '      model_profile: "review_validation"',
            "  retry_policy:",
            "    max_retries_per_stage: 1",
            "    escalate_on:",
            '      - "review"',
            '      - "validate"',
            "",
            "github:",
            '  branch_prefix: "hive/task"',
            '  pr_title_prefix: "[Hive]"',
            "  required_checks:",
            checks_yaml,
            "",
        ]
    )


def _normalize_github_repo(value: str) -> str | None:
    v = (value or "").strip()
    if not v:
        return None
    m = re.search(r"github\.com[:/](?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?$", v)
    if not m:
        return None
    owner = m.group("owner")
    repo = m.group("repo")
    return f"{owner}/{repo}"


def run_project_onboarding(
    *,
    project_id: str,
    repository: str,
    workspace_path: str | None = None,
    stack: str = "node",
    repo_type: str = "single",
    create_manifest: bool = True,
    force_manifest: bool = False,
    dry_run: bool = True,
    dry_run_command: str | None = None,
    command_overrides: dict[str, str] | None = None,
    required_checks: list[str] | None = None,
) -> dict[str, Any]:
    """Run local onboarding checks and optional manifest bootstrap for a project."""
    started = time.time()
    checks: list[dict[str, Any]] = []
    workspace: Path | None = None
    repo_str = (repository or "").strip()

    if stack not in STACKS:
        raise ValueError(f"stack must be one of: {', '.join(sorted(STACKS))}")
    if repo_type not in REPO_TYPES:
        raise ValueError(f"repo_type must be one of: {', '.join(sorted(REPO_TYPES))}")

    if workspace_path:
        workspace = Path(workspace_path).expanduser().resolve()
    elif repo_str and (repo_str.startswith("/") or repo_str.startswith("~")):
        workspace = Path(repo_str).expanduser().resolve()

    github_repo = _normalize_github_repo(repo_str)
    checks.append(
        {
            "id": "github_repo_binding",
            "status": "ok" if github_repo else "warn",
            "message": f"GitHub repo: {github_repo}" if github_repo else "Repository is not a GitHub URL/slug",
        }
    )

    if workspace is None:
        checks.append(
            {
                "id": "workspace_path",
                "status": "warn",
                "message": "workspace_path not provided; manifest bootstrap and dry-run skipped",
            }
        )
        return {
            "project_id": project_id,
            "repository": repo_str,
            "workspace_path": None,
            "github_repo": github_repo,
            "manifest": {"path": None, "created": False, "exists": False},
            "checks": checks,
            "dry_run": {"status": "skipped", "reason": "workspace_path missing"},
            "ready": False,
            "duration_ms": int((time.time() - started) * 1000),
        }

    checks.append(
        {
            "id": "workspace_exists",
            "status": "ok" if workspace.exists() else "fail",
            "message": f"Workspace {workspace}" if workspace.exists() else f"Workspace not found: {workspace}",
        }
    )
    if not workspace.exists():
        return {
            "project_id": project_id,
            "repository": repo_str,
            "workspace_path": str(workspace),
            "github_repo": github_repo,
            "manifest": {"path": str(workspace / "automation" / "hive.manifest.yaml"), "created": False, "exists": False},
            "checks": checks,
            "dry_run": {"status": "skipped", "reason": "workspace_path not found"},
            "ready": False,
            "duration_ms": int((time.time() - started) * 1000),
        }

    git_dir = workspace / ".git"
    checks.append(
        {
            "id": "git_repository",
            "status": "ok" if git_dir.exists() else "warn",
            "message": "Git metadata found" if git_dir.exists() else "No .git directory found",
        }
    )

    readme = workspace / "README.md"
    checks.append(
        {
            "id": "readme",
            "status": "ok" if readme.exists() else "warn",
            "message": "README.md found" if readme.exists() else "README.md is missing",
        }
    )

    required_bins = _required_binaries(stack)
    missing_bins = [name for name in required_bins if shutil.which(name) is None]
    checks.append(
        {
            "id": "toolchain_runtime",
            "status": "ok" if not missing_bins else "fail",
            "message": (
                f"Required binaries found for stack '{stack}'"
                if not missing_bins
                else f"Missing binaries for stack '{stack}': {', '.join(missing_bins)}"
            ),
        }
    )

    manifest_path = workspace / "automation" / "hive.manifest.yaml"
    manifest_created = False
    try:
        if create_manifest and (force_manifest or not manifest_path.exists()):
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            commands = _default_commands(stack)
            if command_overrides:
                for key in ("install", "lint", "typecheck", "test", "build", "smoke"):
                    val = command_overrides.get(key)
                    if isinstance(val, str) and val.strip():
                        commands[key] = val.strip()
            repo_name = github_repo.split("/")[-1] if github_repo else workspace.name
            manifest_path.write_text(
                _manifest_template(
                    repo_name=repo_name,
                    stack=stack,
                    repo_type=repo_type,
                    commands=commands,
                    required_checks=required_checks or [],
                ),
                encoding="utf-8",
            )
            manifest_created = True
    except OSError as e:
        checks.append(
            {
                "id": "manifest_write",
                "status": "fail",
                "message": f"Cannot write manifest: {e}",
            }
        )
        return {
            "project_id": project_id,
            "repository": repo_str,
            "workspace_path": str(workspace),
            "github_repo": github_repo,
            "manifest": {"path": str(manifest_path), "created": False, "exists": manifest_path.exists()},
            "checks": checks,
            "dry_run": {"status": "skipped", "reason": "manifest write failed"},
            "ready": False,
            "duration_ms": int((time.time() - started) * 1000),
        }

    manifest_exists = manifest_path.exists()
    checks.append(
        {
            "id": "manifest",
            "status": "ok" if manifest_exists else "fail",
            "message": str(manifest_path) if manifest_exists else "automation/hive.manifest.yaml missing",
        }
    )

    dry_run_info: dict[str, Any] = {"status": "skipped", "reason": "dry_run=false"}
    if dry_run:
        cmd = (dry_run_command or "test -f automation/hive.manifest.yaml").strip()
        env = os.environ.copy()
        env.setdefault("CI", "1")
        try:
            proc = subprocess.run(
                ["/bin/sh", "-lc", cmd],
                cwd=str(workspace),
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            dry_run_info = {
                "status": "ok" if proc.returncode == 0 else "fail",
                "command": cmd,
                "exit_code": proc.returncode,
                "stdout": (proc.stdout or "").strip()[-4000:],
                "stderr": (proc.stderr or "").strip()[-4000:],
            }
        except subprocess.TimeoutExpired:
            dry_run_info = {
                "status": "fail",
                "command": cmd,
                "error": "dry-run timed out after 120s",
            }
        checks.append(
            {
                "id": "dry_run",
                "status": "ok" if dry_run_info.get("status") == "ok" else "fail",
                "message": f"dry-run command: {cmd}",
            }
        )

    ready = all(c["status"] in {"ok", "warn"} for c in checks) and manifest_exists
    if dry_run:
        ready = ready and dry_run_info.get("status") == "ok"

    return {
        "project_id": project_id,
        "repository": repo_str,
        "workspace_path": str(workspace),
        "github_repo": github_repo,
        "manifest": {
            "path": str(manifest_path),
            "created": manifest_created,
            "exists": manifest_exists,
        },
        "checks": checks,
        "dry_run": dry_run_info,
        "ready": ready,
        "duration_ms": int((time.time() - started) * 1000),
    }

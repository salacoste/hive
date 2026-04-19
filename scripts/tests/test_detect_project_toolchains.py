from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import re
import sys

MODULE_PATH = Path(__file__).resolve().parents[1] / "detect_project_toolchains.py"
SPEC = spec_from_file_location("detect_project_toolchains", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_detect_node_workspace_human(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "node-repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    (repo / "tsconfig.json").write_text("{}\n", encoding="utf-8")

    rc = MODULE.main(["--workspace", str(repo), "--format", "human"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "detected_toolchains: node" in out
    assert "recommended_stack: node" in out
    assert "HIVE_DOCKER_INSTALL_NODE=1" in out
    assert "plan_fingerprint:" in out
    assert re.search(r"confirm_token: APPLY_NODE_[A-F0-9]{8}\b", out)


def test_detect_fullstack_workspace_json(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "fullstack-repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    rc = MODULE.main(["--workspace", str(repo), "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "node" in payload["toolchains"]
    assert "python" in payload["toolchains"]
    assert payload["recommended_stack"] == "fullstack"
    assert payload["docker_build_args"]["HIVE_DOCKER_INSTALL_NODE"] == 1
    assert payload["docker_build_args"]["HIVE_DOCKER_INSTALL_GO"] == 0


def test_detect_go_rust_jvm_env(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "polyglot-repo"
    repo.mkdir()
    (repo / "go.mod").write_text("module demo\n", encoding="utf-8")
    (repo / "Cargo.toml").write_text("[package]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8")
    (repo / "pom.xml").write_text("<project/>", encoding="utf-8")

    rc = MODULE.main(["--workspace", str(repo), "--format", "env"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "HIVE_DOCKER_INSTALL_GO=1" in out
    assert "HIVE_DOCKER_INSTALL_RUST=1" in out
    assert "HIVE_DOCKER_INSTALL_JAVA=1" in out
    assert re.search(r"HIVE_TOOLCHAIN_CONFIRM_TOKEN=APPLY_GO_RUST_JVM_[A-F0-9]{8}\b", out)
    assert re.search(r"HIVE_TOOLCHAIN_PLAN_FINGERPRINT=[A-F0-9]{8}\b", out)


def test_detect_fails_on_missing_workspace(capsys) -> None:
    rc = MODULE.main(["--workspace", "/tmp/not-existing-hive-toolchain-path"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "[fail] workspace not found:" in out


def test_plan_fingerprint_changes_when_markers_change(tmp_path: Path) -> None:
    repo = tmp_path / "mutable-repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")

    first = MODULE.detect_toolchains(repo)
    assert first.plan_fingerprint
    assert first.confirm_token.endswith(first.plan_fingerprint)

    (repo / "go.mod").write_text("module demo\n", encoding="utf-8")
    second = MODULE.detect_toolchains(repo)
    assert second.plan_fingerprint
    assert second.plan_fingerprint != first.plan_fingerprint
    assert second.confirm_token.endswith(second.plan_fingerprint)


def test_normalize_repository_clone_url_adds_https_for_host_path() -> None:
    assert (
        MODULE._normalize_repository_clone_url("github.com/acme/repo")
        == "https://github.com/acme/repo"
    )
    assert (
        MODULE._normalize_repository_clone_url("https://github.com/acme/repo")
        == "https://github.com/acme/repo"
    )
    assert (
        MODULE._normalize_repository_clone_url("git@github.com:acme/repo.git")
        == "git@github.com:acme/repo.git"
    )


def test_clone_repo_uses_normalized_repository_url(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _fake_run(cmd, capture_output, text, check):
        calls.append(list(cmd))
        Path(cmd[-1]).mkdir(parents=True, exist_ok=True)

        class _Proc:
            returncode = 0
            stderr = ""
            stdout = ""

        return _Proc()

    monkeypatch.setattr(MODULE.subprocess, "run", _fake_run)
    root, temp = MODULE._clone_repo("github.com/acme/repo")
    try:
        assert root.exists()
        assert calls
        assert calls[0][4] == "https://github.com/acme/repo"
    finally:
        temp.cleanup()

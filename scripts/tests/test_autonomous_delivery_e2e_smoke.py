from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "autonomous_delivery_e2e_smoke.py"
SPEC = spec_from_file_location("autonomous_delivery_e2e_smoke", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_slug_and_pr_url_helpers() -> None:
    assert MODULE._slug("My Cool Repo!!") == "my-cool-repo"
    assert MODULE._extract_pr_url({"report": {"pr": {"url": "https://github.com/acme/repo/pull/7"}}}) == (
        "https://github.com/acme/repo/pull/7"
    )
    assert MODULE._extract_pr_url({"report": {}}) == ""


def test_resolve_template_repository_fallback() -> None:
    explicit, explicit_source = MODULE._resolve_template_repository("https://github.com/acme/repo")
    assert explicit == "https://github.com/acme/repo"
    assert explicit_source == "explicit"
    fallback, fallback_source = MODULE._resolve_template_repository("")
    assert fallback == MODULE.DEFAULT_TEMPLATE_REPOSITORY
    assert fallback_source == "default_fallback"


def test_issue_reference_detection_helpers() -> None:
    assert MODULE._looks_like_issue_reference("https://github.com/acme/repo/issues/13")
    assert MODULE._looks_like_issue_reference("acme/repo#13")
    assert not MODULE._looks_like_issue_reference("implement a feature without issue ref")
    assert MODULE._is_repo_developer_agent("exports/repo_developer")
    assert MODULE._is_repo_developer_agent("/tmp/exports/repo_developer")
    assert not MODULE._is_repo_developer_agent("exports/n8n_redirect_fixer")


def test_resolve_default_base_url_prefers_explicit_env(monkeypatch) -> None:
    monkeypatch.setenv("HIVE_DELIVERY_E2E_BASE_URL", "http://custom:8787")
    monkeypatch.setenv("HIVE_BASE_URL", "http://shared:8787")
    monkeypatch.setattr(MODULE, "_tcp_endpoint_reachable", lambda *_args, **_kwargs: False)
    assert MODULE._resolve_default_base_url() == "http://custom:8787"


def test_resolve_default_base_url_uses_shared_env_when_explicit_missing(monkeypatch) -> None:
    monkeypatch.delenv("HIVE_DELIVERY_E2E_BASE_URL", raising=False)
    monkeypatch.setenv("HIVE_BASE_URL", "http://shared:8787")
    monkeypatch.setattr(MODULE, "_tcp_endpoint_reachable", lambda *_args, **_kwargs: False)
    assert MODULE._resolve_default_base_url() == "http://shared:8787"


def test_resolve_default_base_url_detects_hive_core_when_localhost_unreachable(monkeypatch) -> None:
    monkeypatch.delenv("HIVE_DELIVERY_E2E_BASE_URL", raising=False)
    monkeypatch.delenv("HIVE_BASE_URL", raising=False)

    def _fake_reachable(host: str, _port: int, *, timeout: float = 0.2) -> bool:
        del timeout
        return host == "hive-core"

    monkeypatch.setattr(MODULE, "_tcp_endpoint_reachable", _fake_reachable)
    assert MODULE._resolve_default_base_url() == "http://hive-core:8787"


def test_ensure_real_project_uses_existing_project() -> None:
    class _Client:
        def request(self, method: str, path: str, payload=None):
            assert method == "GET"
            assert path == "/projects/default"
            return 200, {"id": "default"}

    project_id, created, error = MODULE._ensure_real_project(
        client=_Client(),
        project_id="default",
        repository="https://github.com/acme/repo",
    )
    assert project_id == "default"
    assert created is False
    assert error is None


def test_ensure_real_project_creates_fallback_when_missing(monkeypatch) -> None:
    class _Client:
        def request(self, method: str, path: str, payload=None):
            if method == "GET" and path == "/projects/default":
                return 404, {"error": "not found"}
            if method == "POST" and path == "/projects":
                assert isinstance(payload, dict)
                assert payload["repository"] == "https://github.com/acme/repo"
                return 201, {"id": payload["project_id"]}
            raise AssertionError(f"unexpected call: {method} {path}")

    monkeypatch.setattr(MODULE.time, "time", lambda: 1234567890.0)
    project_id, created, error = MODULE._ensure_real_project(
        client=_Client(),
        project_id="default",
        repository="https://github.com/acme/repo",
    )
    assert project_id == "e2e-real-1234567890"
    assert created is True
    assert error is None


def test_ensure_execution_session_uses_agent_path() -> None:
    calls: list[tuple[str, str, dict | None]] = []

    class _Client:
        def request(self, method: str, path: str, payload=None):
            calls.append((method, path, payload))
            return 201, {"session_id": "session_demo"}

    session_id, error = MODULE._ensure_execution_session(
        client=_Client(),
        project_id="demo-project",
        agent_path="exports/repo_developer",
        session_id="",
        model_profile="implementation",
        model="openai/gemini-3.1-pro-high",
    )
    assert error is None
    assert session_id == "session_demo"
    assert calls == [
        (
            "POST",
            "/sessions",
            {
                "project_id": "demo-project",
                "agent_path": "exports/repo_developer",
                "model_profile": "implementation",
                "model": "openai/gemini-3.1-pro-high",
            },
        )
    ]


def test_run_flow_manual_deferred_when_onboarding_not_ready() -> None:
    class _Client:
        def request(self, method: str, path: str, payload=None):
            if method == "POST" and path.endswith("/onboarding"):
                return 200, {"ready": False, "checks": [{"id": "workspace", "status": "fail"}]}
            if method == "POST" and path.endswith("/autonomous/backlog"):
                return 201, {"id": "task_1"}
            if method == "POST" and path.endswith("/autonomous/execute-next"):
                return 200, {"run_id": "run_1", "terminal": False, "terminal_status": None}
            if method == "GET" and path.endswith("/autonomous/runs/run_1"):
                return 200, {"id": "run_1", "task_id": "task_1"}
            if method == "GET" and path.endswith("/autonomous/runs/run_1/report"):
                return 200, {"report": {}}
            raise AssertionError(f"unexpected call: {method} {path}")

    ok, payload = MODULE._run_flow(
        client=_Client(),
        project_id="default",
        repository="",
        task_title="t",
        task_goal="g",
        acceptance_criteria=["a"],
        max_steps=4,
        onboarding_payload={},
        allow_onboarding_not_ready=True,
    )
    assert ok is True
    assert payload["trace"]["terminal_state"] == "manual_deferred_onboarding"
    assert payload["trace"]["deferred_reason"] == "onboarding_not_ready"
    assert payload["trace"]["task_id"] == "task_1"
    assert payload["trace"]["run_id"] == "run_1"


def test_run_flow_passes_session_id_to_execute_next() -> None:
    class _Client:
        def request(self, method: str, path: str, payload=None):
            if method == "POST" and path.endswith("/onboarding"):
                return 200, {"ready": True, "checks": []}
            if method == "POST" and path.endswith("/autonomous/backlog"):
                return 201, {"id": "task_1"}
            if method == "POST" and path.endswith("/autonomous/execute-next"):
                assert isinstance(payload, dict)
                assert payload.get("session_id") == "session_demo"
                return 200, {"run_id": "run_1", "terminal": False, "terminal_status": None}
            if method == "GET" and path.endswith("/autonomous/runs/run_1"):
                return 200, {"id": "run_1", "task_id": "task_1"}
            if method == "GET" and path.endswith("/autonomous/runs/run_1/report"):
                return 200, {"report": {}}
            raise AssertionError(f"unexpected call: {method} {path}")

    ok, payload = MODULE._run_flow(
        client=_Client(),
        project_id="default",
        repository="",
        task_title="t",
        task_goal="g",
        acceptance_criteria=["a"],
        max_steps=4,
        onboarding_payload={},
        allow_onboarding_not_ready=False,
        session_id="session_demo",
    )
    assert ok is True
    assert payload["trace"]["run_id"] == "run_1"


def test_run_flow_skips_bind_when_disabled() -> None:
    calls: list[tuple[str, str]] = []

    class _Client:
        def request(self, method: str, path: str, payload=None):
            calls.append((method, path))
            if method == "POST" and path.endswith("/onboarding"):
                return 200, {"ready": False, "checks": [{"id": "workspace", "status": "fail"}]}
            if method == "POST" and path.endswith("/autonomous/backlog"):
                return 201, {"id": "task_1"}
            if method == "POST" and path.endswith("/autonomous/execute-next"):
                return 200, {"run_id": "run_1", "terminal": False, "terminal_status": None}
            if method == "GET" and path.endswith("/autonomous/runs/run_1"):
                return 200, {"id": "run_1", "task_id": "task_1"}
            if method == "GET" and path.endswith("/autonomous/runs/run_1/report"):
                return 200, {"report": {}}
            raise AssertionError(f"unexpected call: {method} {path}")

    ok, payload = MODULE._run_flow(
        client=_Client(),
        project_id="default",
        repository="https://github.com/acme/repo",
        task_title="t",
        task_goal="g",
        acceptance_criteria=["a"],
        max_steps=4,
        onboarding_payload={"repository": "https://github.com/acme/repo"},
        allow_onboarding_not_ready=True,
        bind_repository=False,
    )
    assert ok is True
    assert payload["trace"]["terminal_state"] == "manual_deferred_onboarding"
    assert payload["trace"]["task_id"] == "task_1"
    assert payload["trace"]["run_id"] == "run_1"
    assert all(not path.endswith("/repository/bind") for _, path in calls)


def test_run_flow_tolerates_bind_405_with_compatibility_fallback() -> None:
    class _Client:
        def request(self, method: str, path: str, payload=None):
            if method == "POST" and path.endswith("/repository/bind"):
                return 405, {"raw": "405: Method Not Allowed"}
            if method == "POST" and path.endswith("/onboarding"):
                return 200, {"ready": False, "checks": [{"id": "workspace", "status": "fail"}]}
            if method == "POST" and path.endswith("/autonomous/backlog"):
                return 201, {"id": "task_1"}
            if method == "POST" and path.endswith("/autonomous/execute-next"):
                return 200, {"run_id": "run_1", "terminal": False, "terminal_status": None}
            if method == "GET" and path.endswith("/autonomous/runs/run_1"):
                return 200, {"id": "run_1", "task_id": "task_1"}
            if method == "GET" and path.endswith("/autonomous/runs/run_1/report"):
                return 200, {"report": {}}
            raise AssertionError(f"unexpected call: {method} {path}")

    ok, payload = MODULE._run_flow(
        client=_Client(),
        project_id="default",
        repository="https://github.com/acme/repo",
        task_title="t",
        task_goal="g",
        acceptance_criteria=["a"],
        max_steps=4,
        onboarding_payload={"repository": "https://github.com/acme/repo"},
        allow_onboarding_not_ready=True,
        bind_repository=True,
    )
    assert ok is True
    assert payload["trace"]["repository_bind_compatibility_fallback"] is True
    assert payload["trace"]["repository_bind_status"] == 405
    assert payload["trace"]["task_id"] == "task_1"
    assert payload["trace"]["run_id"] == "run_1"


def test_run_flow_fails_when_execute_next_picks_different_task_run() -> None:
    class _Client:
        def request(self, method: str, path: str, payload=None):
            if method == "POST" and path.endswith("/onboarding"):
                return 200, {"ready": True, "checks": []}
            if method == "POST" and path.endswith("/autonomous/backlog"):
                return 201, {"id": "task_1"}
            if method == "POST" and path.endswith("/autonomous/execute-next"):
                return 200, {"run_id": "run_1", "terminal": False, "terminal_status": None}
            if method == "GET" and path.endswith("/autonomous/runs/run_1"):
                return 200, {"id": "run_1", "task_id": "task_existing_active"}
            raise AssertionError(f"unexpected call: {method} {path}")

    ok, payload = MODULE._run_flow(
        client=_Client(),
        project_id="default",
        repository="",
        task_title="t",
        task_goal="g",
        acceptance_criteria=["a"],
        max_steps=4,
        onboarding_payload={},
        allow_onboarding_not_ready=False,
    )
    assert ok is False
    assert payload["error"] == "execute_next selected different active run (task mismatch)"


def test_run_flow_applies_no_checks_policy_patch() -> None:
    class _Client:
        def request(self, method: str, path: str, payload=None):
            if method == "POST" and path.endswith("/onboarding"):
                return 200, {"ready": True, "checks": []}
            if method == "PATCH" and path.endswith("/execution-template"):
                assert payload == {"execution_template": {"no_checks_policy": "success"}}
                return 200, {"effective": {"execution_template": {"no_checks_policy": "success"}}}
            if method == "POST" and path.endswith("/autonomous/backlog"):
                return 201, {"id": "task_1"}
            if method == "POST" and path.endswith("/autonomous/execute-next"):
                return 200, {"run_id": "run_1", "terminal": False, "terminal_status": None}
            if method == "GET" and path.endswith("/autonomous/runs/run_1"):
                return 200, {"id": "run_1", "task_id": "task_1"}
            if method == "GET" and path.endswith("/autonomous/runs/run_1/report"):
                return 200, {"report": {}}
            raise AssertionError(f"unexpected call: {method} {path}")

    ok, payload = MODULE._run_flow(
        client=_Client(),
        project_id="default",
        repository="",
        task_title="t",
        task_goal="g",
        acceptance_criteria=["a"],
        max_steps=4,
        onboarding_payload={},
        allow_onboarding_not_ready=False,
        github_no_checks_policy="success",
    )
    assert ok is True
    assert payload["trace"]["github_no_checks_policy"] == "success"
    assert any(step.get("name") == "execution_template_patch" for step in payload.get("steps", []))


def test_run_flow_requires_terminal_success_when_requested() -> None:
    class _Client:
        def request(self, method: str, path: str, payload=None):
            if method == "POST" and path.endswith("/onboarding"):
                return 200, {"ready": True, "checks": []}
            if method == "POST" and path.endswith("/autonomous/backlog"):
                return 201, {"id": "task_1"}
            if method == "POST" and path.endswith("/autonomous/execute-next"):
                return 200, {"run_id": "run_1", "terminal": False, "terminal_status": None}
            if method == "GET" and path.endswith("/autonomous/runs/run_1"):
                return 200, {"id": "run_1", "task_id": "task_1"}
            if method == "GET" and path.endswith("/autonomous/runs/run_1/report"):
                return 200, {"report": {}}
            if method == "POST" and path.endswith("/autonomous/runs/run_1/run-until-terminal"):
                return 200, {"terminal": True, "terminal_status": "completed"}
            raise AssertionError(f"unexpected call: {method} {path}")

    ok, payload = MODULE._run_flow(
        client=_Client(),
        project_id="default",
        repository="",
        task_title="t",
        task_goal="g",
        acceptance_criteria=["a"],
        max_steps=4,
        onboarding_payload={},
        allow_onboarding_not_ready=False,
        require_terminal_success=True,
    )
    assert ok is True
    assert payload["trace"]["terminal"] is True
    assert payload["trace"]["terminal_status"] == "completed"


def test_run_flow_terminal_failure_is_hard_failure() -> None:
    class _Client:
        def request(self, method: str, path: str, payload=None):
            if method == "POST" and path.endswith("/onboarding"):
                return 200, {"ready": True, "checks": []}
            if method == "POST" and path.endswith("/autonomous/backlog"):
                return 201, {"id": "task_1"}
            if method == "POST" and path.endswith("/autonomous/execute-next"):
                return 200, {"run_id": "run_1", "terminal": False, "terminal_status": None}
            if method == "GET" and path.endswith("/autonomous/runs/run_1"):
                return 200, {"id": "run_1", "task_id": "task_1"}
            if method == "GET" and path.endswith("/autonomous/runs/run_1/report"):
                return 200, {"report": {}}
            if method == "POST" and path.endswith("/autonomous/runs/run_1/run-until-terminal"):
                return 200, {"terminal": True, "terminal_status": "failed"}
            raise AssertionError(f"unexpected call: {method} {path}")

    ok, payload = MODULE._run_flow(
        client=_Client(),
        project_id="default",
        repository="",
        task_title="t",
        task_goal="g",
        acceptance_criteria=["a"],
        max_steps=4,
        onboarding_payload={},
        allow_onboarding_not_ready=False,
        require_terminal_success=True,
    )
    assert ok is False
    assert payload["error"] == "run terminal status is failed"


def test_run_flow_fails_when_onboarding_not_ready_in_strict_mode() -> None:
    class _Client:
        def request(self, method: str, path: str, payload=None):
            if method == "POST" and path.endswith("/onboarding"):
                return 200, {"ready": False, "checks": [{"id": "workspace", "status": "fail"}]}
            raise AssertionError(f"unexpected call: {method} {path}")

    ok, payload = MODULE._run_flow(
        client=_Client(),
        project_id="default",
        repository="",
        task_title="t",
        task_goal="g",
        acceptance_criteria=["a"],
        max_steps=4,
        onboarding_payload={},
        allow_onboarding_not_ready=False,
    )
    assert ok is False
    assert payload["error"] == "onboarding is not ready"


def test_main_skips_real_scenario_without_repository(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["autonomous_delivery_e2e_smoke.py", "--skip-template"])
    rc = MODULE.main()
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["status"] == "ok"
    assert payload["scenarios_total"] == 1
    assert payload["scenarios_skipped"] == 1
    assert payload["results"][0]["scenario"] == "real_repo"
    assert payload["results"][0]["reason"] == "real_repository_not_configured"


def test_main_real_scenario_uses_project_workspace_for_onboarding(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, method: str, path: str, payload=None):
            if method == "GET" and path == "/projects/demo":
                return 200, {"id": "demo", "workspace_path": "/tmp/demo-workspace"}
            raise AssertionError(f"unexpected call: {method} {path}")

    def _fake_run_flow(*, onboarding_payload, **_kwargs):
        captured["onboarding_payload"] = dict(onboarding_payload)
        return True, {"steps": [], "trace": {"task_id": "task_1", "run_id": "run_1"}}

    monkeypatch.setattr(MODULE, "ApiClient", _Client)
    monkeypatch.setattr(MODULE, "_ensure_real_project", lambda **_kwargs: ("demo", False, None))
    monkeypatch.setattr(MODULE, "_run_flow", _fake_run_flow)
    monkeypatch.setattr(
        "sys.argv",
        [
            "autonomous_delivery_e2e_smoke.py",
            "--skip-template",
            "--real-project-id",
            "demo",
            "--real-repository",
            "https://github.com/acme/repo",
        ],
    )

    rc = MODULE.main()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["scenarios_ok"] == 1
    assert captured["onboarding_payload"] == {
        "repository": "https://github.com/acme/repo",
        "workspace_path": "/tmp/demo-workspace",
    }


def test_main_real_scenario_passes_stack_override(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, method: str, path: str, payload=None):
            if method == "GET" and path == "/projects/demo":
                return 200, {"id": "demo", "workspace_path": "/tmp/demo-workspace"}
            raise AssertionError(f"unexpected call: {method} {path}")

    def _fake_run_flow(*, onboarding_payload, **_kwargs):
        captured["onboarding_payload"] = dict(onboarding_payload)
        return True, {"steps": [], "trace": {"task_id": "task_1", "run_id": "run_1"}}

    monkeypatch.setattr(MODULE, "ApiClient", _Client)
    monkeypatch.setattr(MODULE, "_ensure_real_project", lambda **_kwargs: ("demo", False, None))
    monkeypatch.setattr(MODULE, "_run_flow", _fake_run_flow)
    monkeypatch.setattr(
        "sys.argv",
        [
            "autonomous_delivery_e2e_smoke.py",
            "--skip-template",
            "--real-project-id",
            "demo",
            "--real-repository",
            "https://github.com/acme/repo",
            "--real-stack",
            "python",
        ],
    )

    rc = MODULE.main()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert captured["onboarding_payload"] == {
        "repository": "https://github.com/acme/repo",
        "workspace_path": "/tmp/demo-workspace",
        "stack": "python",
    }


def test_main_repo_developer_requires_issue_reference(monkeypatch, capsys) -> None:
    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, method: str, path: str, payload=None):
            if method == "GET" and path == "/projects/demo":
                return 200, {"id": "demo", "workspace_path": "/tmp/demo-workspace"}
            raise AssertionError(f"unexpected call: {method} {path}")

    monkeypatch.setattr(MODULE, "ApiClient", _Client)
    monkeypatch.setattr(MODULE, "_ensure_real_project", lambda **_kwargs: ("demo", False, None))
    monkeypatch.setattr(MODULE, "_ensure_execution_session", lambda **_kwargs: ("session_demo", None))
    monkeypatch.setattr(
        "sys.argv",
        [
            "autonomous_delivery_e2e_smoke.py",
            "--skip-template",
            "--real-project-id",
            "demo",
            "--real-repository",
            "https://github.com/acme/repo",
            "--real-agent-path",
            "exports/repo_developer",
            "--real-task-goal",
            "do work without issue url",
        ],
    )

    rc = MODULE.main()
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["results"][0]["error"].startswith("repo_developer requires issue reference")

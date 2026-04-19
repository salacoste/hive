"""Persistent backlog + autonomous pipeline run state per project."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STAGES: tuple[str, ...] = ("execution", "review", "validation")


@dataclass
class BacklogTask:
    id: str
    project_id: str
    title: str
    goal: str
    acceptance_criteria: list[str]
    status: str = "todo"  # todo|in_progress|done|blocked
    priority: str = "medium"  # low|medium|high|critical
    repository: str = ""
    branch: str = ""
    required_checks: list[str] = field(default_factory=list)
    workflow: str = ""
    service_matrix: list[str] = field(default_factory=list)
    validation_mode: str = "ci_first"  # ci_first|local_or_ci
    validation_reason: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class PipelineRun:
    id: str
    project_id: str
    task_id: str
    status: str  # queued|in_progress|completed|failed|escalated
    current_stage: str
    stage_states: dict[str, str]
    attempts: dict[str, int]
    artifacts: dict[str, Any]
    started_at: float
    updated_at: float
    finished_at: float | None = None


class AutonomousPipelineStore:
    """JSON-backed storage for backlog tasks and pipeline runs."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (Path.home() / ".hive" / "server" / "autonomous_pipeline.json")
        self._tasks: dict[str, BacklogTask] = {}
        self._runs: dict[str, PipelineRun] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for item in payload.get("tasks", []):
            try:
                task = BacklogTask(**item)
            except TypeError:
                continue
            self._tasks[task.id] = task
        for item in payload.get("runs", []):
            try:
                run = PipelineRun(**item)
            except TypeError:
                continue
            self._runs[run.id] = run

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tasks = sorted(self._tasks.values(), key=lambda x: x.updated_at, reverse=True)
        runs = sorted(self._runs.values(), key=lambda x: x.updated_at, reverse=True)
        payload = {
            "tasks": [asdict(x) for x in tasks],
            "runs": [asdict(x) for x in runs],
        }
        self._path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def list_tasks(self, *, project_id: str, status: str | None = None) -> list[BacklogTask]:
        tasks = [t for t in self._tasks.values() if t.project_id == project_id]
        if status:
            tasks = [t for t in tasks if t.status == status]
        tasks.sort(key=lambda x: x.updated_at, reverse=True)
        return tasks

    def list_all_tasks(self) -> list[BacklogTask]:
        tasks = list(self._tasks.values())
        tasks.sort(key=lambda x: x.updated_at, reverse=True)
        return tasks

    def get_task(self, task_id: str) -> BacklogTask | None:
        return self._tasks.get(task_id)

    def create_task(
        self,
        *,
        project_id: str,
        title: str,
        goal: str,
        acceptance_criteria: list[str],
        priority: str = "medium",
        repository: str = "",
        branch: str = "",
        required_checks: list[str] | None = None,
        workflow: str = "",
        service_matrix: list[str] | None = None,
        validation_mode: str = "ci_first",
        validation_reason: str = "",
    ) -> BacklogTask:
        now = time.time()
        task = BacklogTask(
            id=f"task_{uuid.uuid4().hex[:10]}",
            project_id=project_id,
            title=title,
            goal=goal,
            acceptance_criteria=acceptance_criteria,
            priority=priority,
            repository=repository,
            branch=branch,
            required_checks=list(required_checks or []),
            workflow=workflow,
            service_matrix=list(service_matrix or []),
            validation_mode=validation_mode,
            validation_reason=validation_reason,
            created_at=now,
            updated_at=now,
        )
        self._tasks[task.id] = task
        self._save()
        return task

    def update_task(self, task_id: str, updates: dict[str, Any]) -> BacklogTask | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        if "title" in updates and isinstance(updates["title"], str):
            task.title = updates["title"].strip() or task.title
        if "goal" in updates and isinstance(updates["goal"], str):
            task.goal = updates["goal"].strip() or task.goal
        if "acceptance_criteria" in updates and isinstance(updates["acceptance_criteria"], list):
            task.acceptance_criteria = [str(x).strip() for x in updates["acceptance_criteria"] if str(x).strip()]
        if "status" in updates and isinstance(updates["status"], str):
            task.status = updates["status"]
        if "priority" in updates and isinstance(updates["priority"], str):
            task.priority = updates["priority"]
        if "repository" in updates and isinstance(updates["repository"], str):
            task.repository = updates["repository"].strip()
        if "branch" in updates and isinstance(updates["branch"], str):
            task.branch = updates["branch"].strip()
        if "required_checks" in updates and isinstance(updates["required_checks"], list):
            task.required_checks = [str(x).strip() for x in updates["required_checks"] if str(x).strip()]
        if "workflow" in updates and isinstance(updates["workflow"], str):
            task.workflow = updates["workflow"].strip()
        if "service_matrix" in updates and isinstance(updates["service_matrix"], list):
            task.service_matrix = [str(x).strip() for x in updates["service_matrix"] if str(x).strip()]
        if "validation_mode" in updates and isinstance(updates["validation_mode"], str):
            task.validation_mode = updates["validation_mode"].strip()
        if "validation_reason" in updates and isinstance(updates["validation_reason"], str):
            task.validation_reason = updates["validation_reason"].strip()
        task.updated_at = time.time()
        self._save()
        return task

    def list_runs(self, *, project_id: str) -> list[PipelineRun]:
        runs = [r for r in self._runs.values() if r.project_id == project_id]
        runs.sort(key=lambda x: x.updated_at, reverse=True)
        return runs

    def list_all_runs(self) -> list[PipelineRun]:
        runs = list(self._runs.values())
        runs.sort(key=lambda x: x.updated_at, reverse=True)
        return runs

    def get_run(self, run_id: str) -> PipelineRun | None:
        return self._runs.get(run_id)

    def create_run(self, *, project_id: str, task_id: str) -> PipelineRun:
        now = time.time()
        stage_states = {stage: "pending" for stage in STAGES}
        stage_states[STAGES[0]] = "queued"
        run = PipelineRun(
            id=f"run_{uuid.uuid4().hex[:10]}",
            project_id=project_id,
            task_id=task_id,
            status="queued",
            current_stage=STAGES[0],
            stage_states=stage_states,
            attempts={stage: 0 for stage in STAGES},
            artifacts={"report": {}, "stages": {}},
            started_at=now,
            updated_at=now,
            finished_at=None,
        )
        self._runs[run.id] = run
        self._save()
        return run

    def update_run(self, run_id: str, mutate: dict[str, Any]) -> PipelineRun | None:
        run = self._runs.get(run_id)
        if run is None:
            return None
        for key, value in mutate.items():
            if hasattr(run, key):
                setattr(run, key, value)
        run.updated_at = time.time()
        self._save()
        return run

    def delete_project_state(self, project_id: str) -> dict[str, int]:
        """Remove all backlog tasks and pipeline runs for a project."""
        removed_tasks = 0
        removed_runs = 0

        task_ids = [task_id for task_id, task in self._tasks.items() if task.project_id == project_id]
        for task_id in task_ids:
            self._tasks.pop(task_id, None)
            removed_tasks += 1

        run_ids = [run_id for run_id, run in self._runs.items() if run.project_id == project_id]
        for run_id in run_ids:
            self._runs.pop(run_id, None)
            removed_runs += 1

        if removed_tasks or removed_runs:
            self._save()
        return {"tasks_removed": removed_tasks, "runs_removed": removed_runs}

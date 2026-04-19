import { api } from "./client";

export type BacklogTask = {
  id: string;
  project_id: string;
  title: string;
  goal: string;
  acceptance_criteria: string[];
  status: "todo" | "in_progress" | "done" | "blocked";
  priority: "low" | "medium" | "high" | "critical";
  repository: string;
  branch: string;
  created_at: number;
  updated_at: number;
};

export type PipelineRun = {
  id: string;
  project_id: string;
  task_id: string;
  status: "queued" | "in_progress" | "completed" | "failed" | "escalated";
  current_stage: "execution" | "review" | "validation";
  stage_states: Record<string, string>;
  attempts: Record<string, number>;
  artifacts: Record<string, unknown>;
  started_at: number;
  updated_at: number;
  finished_at?: number | null;
};

export type DispatchNextResponse = {
  project_id: string;
  selected_task: BacklogTask;
  run: PipelineRun;
  selection: { strategy: string };
};

export type LoopTickResponse = {
  action: string;
  project_id?: string;
  reason?: string;
  deferred?: boolean;
  status?: number;
  selected_task?: BacklogTask;
  run?: PipelineRun;
};

export type LoopRunCycleResponse = {
  status: "ok" | "partial";
  summary: {
    projects_total: number;
    ok: number;
    failed: number;
    max_steps_per_project: number;
    outcomes?: Record<string, number>;
  };
  results: Array<{
    project_id: string;
    status: number;
    steps_executed: number;
    steps: Array<{ status: number; action?: string; error?: string; reason?: string }>;
    outcome?: string;
    terminal?: boolean;
    terminal_status?: "completed" | "failed" | "escalated" | string;
    terminal_run_id?: string;
    pr_ready?: boolean;
    pr_url?: string;
    run_id?: string;
    run_status?: string;
    current_stage?: string;
    action?: string;
    error?: string;
    reason?: string;
    run?: PipelineRun;
  }>;
};

export type RunUntilTerminalResponse = {
  project_id: string;
  run_id: string;
  terminal: boolean;
  terminal_status?: "completed" | "failed" | "escalated" | string | null;
  current_stage?: string;
  status?: string;
  steps_executed: number;
  max_steps: number;
  action?: string;
  steps: Array<{ status: number; action?: string; error?: string; reason?: string }>;
  run: PipelineRun;
  selected_task?: BacklogTask;
};

export type AutonomousOpsStatusResponse = {
  status: "ok" | string;
  timestamp: number;
  summary: {
    project_filter?: string | null;
    include_runs?: boolean;
    projects_total: number;
    projects_with_pipeline_state: number;
    tasks_total: number;
    runs_total: number;
    docker_lane_enabled?: boolean;
    docker_lane_ready?: boolean;
    tasks_by_status: Record<string, number>;
    runs_by_status: Record<string, number>;
    runs_by_stage: Record<string, number>;
  };
  alerts: {
    stuck_threshold_seconds: number;
    stuck_runs_total: number;
    no_progress_threshold_seconds: number;
    no_progress_projects_total: number;
    loop_stale_threshold_seconds?: number;
    loop_stale?: boolean;
    loop_stale_seconds?: number;
  };
  active_runs: Array<{
    project_id: string;
    run_id: string;
    status: string;
    current_stage: string;
    updated_at: number;
    no_progress_seconds: number;
  }>;
  projects: Record<string, unknown>;
  runtime?: {
    docker_lane?: {
      enabled?: boolean;
      profile?: string;
      feature_flag?: string;
      docker_cli_available?: boolean;
      docker_cli_path?: string;
      healthcheck_timeout_seconds?: number;
      ready?: boolean;
      status?: string;
      reason?: string;
      server_version?: string;
      error?: string;
    };
  };
  loop?: {
    state_path?: string;
    stale?: boolean;
    stale_seconds?: number;
    stale_threshold_seconds?: number;
    state?: Record<string, unknown>;
  };
};

export type AutonomousRemediateStaleResponse = {
  status: "ok" | string;
  dry_run: boolean;
  project_filter?: string | null;
  action: "failed" | "escalated" | string;
  older_than_seconds: number;
  max_runs: number;
  candidates_total: number;
  selected_total: number;
  selected: Array<{
    project_id: string;
    run_id: string;
    task_id: string;
    status: string;
    current_stage: string;
    updated_at: number;
    stale_for_seconds: number;
  }>;
  remediated_total: number;
  remediated: Array<{
    project_id: string;
    run_id: string;
    task_id: string;
    from_status: string;
    to_status: string;
    stale_for_seconds: number;
  }>;
};

export const autonomousApi = {
  listBacklog: (projectId: string, status?: BacklogTask["status"]) =>
    api.get<{ project_id: string; tasks: BacklogTask[] }>(
      `/projects/${encodeURIComponent(projectId)}/autonomous/backlog${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),

  createBacklogTask: (
    projectId: string,
    payload: {
      title: string;
      goal: string;
      acceptance_criteria: string[];
      priority?: BacklogTask["priority"];
      repository?: string;
      branch?: string;
    },
  ) => api.post<BacklogTask>(`/projects/${encodeURIComponent(projectId)}/autonomous/backlog`, payload),

  updateBacklogTask: (
    projectId: string,
    taskId: string,
    patch: Partial<Pick<BacklogTask, "title" | "goal" | "acceptance_criteria" | "status" | "priority" | "repository" | "branch">>,
  ) => api.patch<BacklogTask>(`/projects/${encodeURIComponent(projectId)}/autonomous/backlog/${encodeURIComponent(taskId)}`, patch),

  listRuns: (projectId: string) =>
    api.get<{ project_id: string; runs: PipelineRun[] }>(`/projects/${encodeURIComponent(projectId)}/autonomous/runs`),

  createRun: (projectId: string, payload: { task_id: string; auto_start?: boolean; session_id?: string }) =>
    api.post<PipelineRun>(`/projects/${encodeURIComponent(projectId)}/autonomous/runs`, payload),

  dispatchNextRun: (projectId: string, payload?: { auto_start?: boolean; session_id?: string }) =>
    api.post<DispatchNextResponse>(`/projects/${encodeURIComponent(projectId)}/autonomous/dispatch-next`, payload || {}),

  executeNextRun: (
    projectId: string,
    payload?: {
      auto_start?: boolean;
      session_id?: string;
      max_steps?: number;
      repository?: string;
      ref?: string;
      pr_url?: string;
      required_checks?: string[];
      notes?: string;
      summary?: string;
    },
  ) => api.post<RunUntilTerminalResponse>(`/projects/${encodeURIComponent(projectId)}/autonomous/execute-next`, payload || {}),

  loopTick: (
    projectId: string,
    payload?: {
      auto_start?: boolean;
      session_id?: string;
      repository?: string;
      ref?: string;
      pr_url?: string;
      required_checks?: string[];
      notes?: string;
      summary?: string;
    },
  ) => api.post<LoopTickResponse>(`/projects/${encodeURIComponent(projectId)}/autonomous/loop/tick`, payload || {}),

  runCycle: (
    payload?: {
      project_ids?: string[];
      auto_start?: boolean;
      max_steps_per_project?: number;
      session_id_by_project?: Record<string, string>;
      repository?: string;
      ref?: string;
      pr_url?: string;
      required_checks?: string[];
      notes?: string;
      summary?: string;
    },
  ) => api.post<LoopRunCycleResponse>("/autonomous/loop/run-cycle", payload || {}),

  opsStatus: (payload?: { project_id?: string; include_runs?: boolean }) => {
    const params = new URLSearchParams();
    if (payload?.project_id) params.set("project_id", payload.project_id);
    if (payload?.include_runs) params.set("include_runs", "true");
    const query = params.toString();
    return api.get<AutonomousOpsStatusResponse>(`/autonomous/ops/status${query ? `?${query}` : ""}`);
  },

  remediateStaleRuns: (
    payload?: {
      project_id?: string;
      older_than_seconds?: number;
      max_runs?: number;
      dry_run?: boolean;
      confirm?: boolean;
      action?: "failed" | "escalated";
      reason?: string;
    },
  ) => api.post<AutonomousRemediateStaleResponse>("/autonomous/ops/remediate-stale", payload || {}),

  getRun: (projectId: string, runId: string) =>
    api.get<PipelineRun>(`/projects/${encodeURIComponent(projectId)}/autonomous/runs/${encodeURIComponent(runId)}`),

  report: (projectId: string, runId: string) =>
    api.get<{
      run_id: string;
      project_id: string;
      task_id: string;
      status: PipelineRun["status"];
      current_stage: PipelineRun["current_stage"];
      attempts: Record<string, number>;
      report: Record<string, unknown>;
      stages: Record<string, unknown>;
    }>(`/projects/${encodeURIComponent(projectId)}/autonomous/runs/${encodeURIComponent(runId)}/report`),

  advanceRun: (
    projectId: string,
    runId: string,
    payload: {
      stage?: "execution" | "review" | "validation";
      result: "success" | "failed";
      notes?: string;
      output?: Record<string, unknown>;
      pr_url?: string;
      summary?: string;
    },
  ) =>
    api.post<PipelineRun>(`/projects/${encodeURIComponent(projectId)}/autonomous/runs/${encodeURIComponent(runId)}/advance`, payload),

  evaluateRun: (
    projectId: string,
    runId: string,
    payload: {
      stage?: "execution" | "review" | "validation";
      source?: string;
      checks: Array<{ name: string; passed: boolean; severity?: "warning" | "error"; details?: string }>;
      notes?: string;
      summary?: string;
      pr_url?: string;
    },
  ) =>
    api.post<PipelineRun>(
      `/projects/${encodeURIComponent(projectId)}/autonomous/runs/${encodeURIComponent(runId)}/evaluate`,
      payload,
    ),

  evaluateRunFromGitHub: (
    projectId: string,
    runId: string,
    payload: {
      stage?: "execution" | "review" | "validation";
      repository: string;
      ref: string;
      required_checks?: string[];
      notes?: string;
      summary?: string;
      pr_url?: string;
    },
  ) =>
    api.post<PipelineRun>(
      `/projects/${encodeURIComponent(projectId)}/autonomous/runs/${encodeURIComponent(runId)}/evaluate/github`,
      payload,
    ),

  autoNextRun: (
    projectId: string,
    runId: string,
    payload?: {
      repository?: string;
      ref?: string;
      pr_url?: string;
      required_checks?: string[];
      notes?: string;
      summary?: string;
    },
  ) =>
    api.post<PipelineRun>(
      `/projects/${encodeURIComponent(projectId)}/autonomous/runs/${encodeURIComponent(runId)}/auto-next`,
      payload || {},
    ),

  runUntilTerminal: (
    projectId: string,
    runId: string,
    payload?: {
      max_steps?: number;
      auto_start?: boolean;
      session_id?: string;
      repository?: string;
      ref?: string;
      pr_url?: string;
      required_checks?: string[];
      notes?: string;
      summary?: string;
    },
  ) =>
    api.post<RunUntilTerminalResponse>(
      `/projects/${encodeURIComponent(projectId)}/autonomous/runs/${encodeURIComponent(runId)}/run-until-terminal`,
      payload || {},
    ),
};

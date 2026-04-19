import { api } from "./client";
import type { ProjectInfo, LiveSession } from "./types";

export const projectsApi = {
  list: () =>
    api.get<{ default_project_id: string; projects: ProjectInfo[] }>("/projects"),

  templates: () =>
    api.get<{
      templates: Array<{
        id: string;
        name: string;
        description: string;
        stack: "node" | "python" | "go" | "jvm" | "rust" | "fullstack";
        repo_type: "single" | "monorepo";
        required_checks: string[];
        commands: Partial<Record<"install" | "lint" | "typecheck" | "test" | "build" | "smoke", string>>;
        dry_run_command?: string;
      }>;
    }>("/projects/templates"),

  compareMetrics: () =>
    api.get<{
      projects: Array<{
        project: { id: string; name: string; repository: string };
        summary: {
          active_sessions: number;
          historical_sessions: number;
          executions_total: number;
          messages_total: number;
          user_messages_total: number;
        };
        kpis: {
          success_rate: number | null;
          cycle_time_seconds_p50: number | null;
          cycle_time_seconds_avg: number | null;
          intervention_ratio: number;
        };
      }>;
    }>("/projects/metrics"),

  get: (projectId: string) =>
    api.get<ProjectInfo>(`/projects/${encodeURIComponent(projectId)}`),

  create: (
    name: string,
    description?: string,
    repository?: string,
    projectId?: string,
    maxConcurrentRuns?: number | null,
    policyOverrides?: {
      risk_tier?: "low" | "medium" | "high" | "critical";
      retry_limit_per_stage?: number | null;
      budget_limit_usd_monthly?: number | null;
    } | null,
    policyBinding?: {
      risk_tier?: "low" | "medium" | "high" | "critical";
      retry_limit_per_stage?: number | null;
      budget_limit_usd_monthly?: number | null;
    } | null,
    executionTemplate?: {
      default_flow?: Array<{ stage: string; mode: string; model_profile: string }>;
      retry_policy?: {
        max_retries_per_stage?: number | null;
        escalate_on?: string[] | null;
      };
      github?: {
        default_ref?: string | null;
        default_branch?: string | null;
        ref?: string | null;
        branch?: string | null;
        no_checks_policy?: "error" | "success" | "manual_pending" | "manual" | "defer" | "pass" | "ok" | null;
      } | null;
      default_ref?: string | null;
      default_branch?: string | null;
      ref?: string | null;
      branch?: string | null;
      no_checks_policy?: "error" | "success" | "manual_pending" | "manual" | "defer" | "pass" | "ok" | null;
    } | null,
  ) =>
    api.post<ProjectInfo>("/projects", {
      name,
      description: description || "",
      repository: repository || "",
      project_id: projectId || undefined,
      max_concurrent_runs: maxConcurrentRuns ?? undefined,
      policy_overrides: policyOverrides ?? undefined,
      policy_binding: policyBinding ?? undefined,
      execution_template: executionTemplate ?? undefined,
    }),

  update: (
    projectId: string,
    patch: Partial<Pick<ProjectInfo, "name" | "description" | "repository" | "max_concurrent_runs">>,
  ) =>
    api.patch<ProjectInfo>(`/projects/${encodeURIComponent(projectId)}`, patch),

  delete: (projectId: string, force = false) =>
    api.delete<{ deleted: string }>(
      `/projects/${encodeURIComponent(projectId)}${force ? "?force=1" : ""}`,
    ),

  sessions: (projectId: string) =>
    api.get<{ sessions: Array<Pick<LiveSession, "session_id" | "project_id" | "graph_id" | "has_worker" | "loaded_at" | "agent_path">> }>(
      `/projects/${encodeURIComponent(projectId)}/sessions`,
    ),

  metrics: (projectId: string) =>
    api.get<{
      project_id: string;
      summary: {
        active_sessions: number;
        historical_sessions: number;
        executions_total: number;
        messages_total: number;
        user_messages_total: number;
      };
      kpis: {
        success_rate: number | null;
        cycle_time_seconds_p50: number | null;
        cycle_time_seconds_avg: number | null;
        intervention_ratio: number;
      };
    }>(`/projects/${encodeURIComponent(projectId)}/metrics`),

  policy: (projectId: string) =>
    api.get<{
      project_id: string;
      global_policy: Record<string, unknown>;
      overrides: Record<string, unknown>;
      effective: Record<string, unknown>;
    }>(`/projects/${encodeURIComponent(projectId)}/policy`),

  updatePolicy: (
    projectId: string,
    patch: {
      risk_tier?: "low" | "medium" | "high" | "critical" | null;
      retry_limit_per_stage?: number | null;
      budget_limit_usd_monthly?: number | null;
    },
  ) =>
    api.patch<{
      project_id: string;
      global_policy: Record<string, unknown>;
      overrides: Record<string, unknown>;
      effective: Record<string, unknown>;
    }>(`/projects/${encodeURIComponent(projectId)}/policy`, patch),

  executionTemplate: (projectId: string) =>
    api.get<{
      project_id: string;
      defaults: {
        execution_template: {
          default_flow: Array<{ stage: string; mode: string; model_profile: string }>;
          retry_policy: { max_retries_per_stage: number; escalate_on: string[] };
          github?: {
            default_ref?: string;
            default_branch?: string;
            ref?: string;
            branch?: string;
            no_checks_policy?: "error" | "success" | "manual_pending";
          };
          default_ref?: string;
          default_branch?: string;
          ref?: string;
          branch?: string;
          no_checks_policy?: "error" | "success" | "manual_pending";
        };
        policy_binding: Record<string, unknown>;
      };
      execution_template: {
        default_flow?: Array<{ stage: string; mode: string; model_profile: string }>;
        retry_policy?: { max_retries_per_stage?: number; escalate_on?: string[] };
        github?: {
          default_ref?: string;
          default_branch?: string;
          ref?: string;
          branch?: string;
          no_checks_policy?: "error" | "success" | "manual_pending" | "manual" | "defer" | "pass" | "ok";
        };
        default_ref?: string;
        default_branch?: string;
        ref?: string;
        branch?: string;
        no_checks_policy?: "error" | "success" | "manual_pending" | "manual" | "defer" | "pass" | "ok";
      };
      policy_binding: {
        risk_tier?: "low" | "medium" | "high" | "critical";
        retry_limit_per_stage?: number;
        budget_limit_usd_monthly?: number;
      };
      effective: {
        execution_template: {
          default_flow: Array<{ stage: string; mode: string; model_profile: string }>;
          retry_policy: { max_retries_per_stage: number; escalate_on: string[] };
          github?: {
            default_ref?: string;
            default_branch?: string;
            ref?: string;
            branch?: string;
            no_checks_policy?: "error" | "success" | "manual_pending";
          };
          default_ref?: string;
          default_branch?: string;
          ref?: string;
          branch?: string;
          no_checks_policy?: "error" | "success" | "manual_pending";
        };
        policy: Record<string, unknown>;
      };
    }>(`/projects/${encodeURIComponent(projectId)}/execution-template`),

  updateExecutionTemplate: (
    projectId: string,
    patch: {
      execution_template?: {
        default_flow?: Array<{ stage: string; mode: string; model_profile: string }> | null;
        retry_policy?: {
          max_retries_per_stage?: number | null;
          escalate_on?: string[] | null;
        } | null;
        github?: {
          default_ref?: string | null;
          default_branch?: string | null;
          ref?: string | null;
          branch?: string | null;
          no_checks_policy?: "error" | "success" | "manual_pending" | "manual" | "defer" | "pass" | "ok" | null;
        } | null;
        default_ref?: string | null;
        default_branch?: string | null;
        ref?: string | null;
        branch?: string | null;
        no_checks_policy?: "error" | "success" | "manual_pending" | "manual" | "defer" | "pass" | "ok" | null;
      };
      policy_binding?: {
        risk_tier?: "low" | "medium" | "high" | "critical";
        retry_limit_per_stage?: number | null;
        budget_limit_usd_monthly?: number | null;
      };
    },
  ) =>
    api.patch<{
      project_id: string;
      defaults: Record<string, unknown>;
      execution_template: Record<string, unknown>;
      policy_binding: Record<string, unknown>;
      effective: Record<string, unknown>;
    }>(`/projects/${encodeURIComponent(projectId)}/execution-template`, patch),

  retention: (projectId: string) =>
    api.get<{
      project_id: string;
      defaults: Record<string, unknown>;
      overrides: Record<string, unknown>;
      effective: {
        history_days: number;
        min_sessions_to_keep: number;
        archive_enabled: boolean;
        archive_root: string;
      };
      plan: {
        historical_sessions: number;
        eligible_count: number;
        cutoff_timestamp: number;
        candidates: Array<{ session_id: string; created_at: number; age_days: number }>;
      };
    }>(`/projects/${encodeURIComponent(projectId)}/retention`),

  updateRetention: (
    projectId: string,
    patch: {
      history_days?: number | null;
      min_sessions_to_keep?: number | null;
      archive_enabled?: boolean;
      archive_root?: string | null;
    },
  ) =>
    api.patch<{
      project_id: string;
      defaults: Record<string, unknown>;
      overrides: Record<string, unknown>;
      effective: Record<string, unknown>;
    }>(`/projects/${encodeURIComponent(projectId)}/retention`, patch),

  applyRetention: (
    projectId: string,
    payload?: {
      dry_run?: boolean;
      history_days?: number;
      min_sessions_to_keep?: number;
      archive_enabled?: boolean;
      archive_root?: string;
    },
  ) =>
    api.post<{
      dry_run: boolean;
      policy: Record<string, unknown>;
      plan: Record<string, unknown>;
      applied?: Record<string, unknown>;
    }>(`/projects/${encodeURIComponent(projectId)}/retention/apply`, payload || {}),

  onboarding: (
    projectId: string,
    payload: {
      template_id?: string;
      repository?: string;
      workspace_path?: string;
      stack?: "node" | "python" | "go" | "jvm" | "rust" | "fullstack";
      repo_type?: "single" | "monorepo";
      create_manifest?: boolean;
      force_manifest?: boolean;
      dry_run?: boolean;
      dry_run_command?: string;
      commands?: Partial<Record<"install" | "lint" | "typecheck" | "test" | "build" | "smoke", string>>;
      required_checks?: string[];
    },
  ) =>
    api.post<{
      project_id: string;
      repository: string;
      workspace_path: string | null;
      github_repo: string | null;
      ready: boolean;
      duration_ms: number;
      manifest: { path: string | null; created: boolean; exists: boolean };
      checks: Array<{ id: string; status: "ok" | "warn" | "fail"; message: string }>;
      dry_run: Record<string, unknown>;
    }>(`/projects/${encodeURIComponent(projectId)}/onboarding`, payload),

  toolchainProfile: (projectId: string) =>
    api.get<{
      project_id: string;
      toolchain_profile: Record<string, unknown>;
    }>(`/projects/${encodeURIComponent(projectId)}/toolchain-profile`),

  planToolchainProfile: (
    projectId: string,
    payload: {
      workspace_path?: string;
      repository?: string;
    },
  ) =>
    api.post<{
      project_id: string;
      pending_plan: Record<string, unknown>;
      instructions: {
        preview_command: string;
        apply_command: string;
        env_exports: string[];
      };
    }>(`/projects/${encodeURIComponent(projectId)}/toolchain-profile/plan`, payload),

  approveToolchainProfile: (
    projectId: string,
    payload: {
      confirm_token: string;
      revalidate?: boolean;
    },
  ) =>
    api.post<{
      project_id: string;
      status: "approved";
      approved_plan: Record<string, unknown>;
      instructions: {
        preview_command: string;
        apply_command: string;
        env_exports: string[];
      };
    }>(`/projects/${encodeURIComponent(projectId)}/toolchain-profile/approve`, payload),
};

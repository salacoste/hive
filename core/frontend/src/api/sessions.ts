import { api } from "./client";
import type {
  AgentEvent,
  HistorySession,
  LiveSession,
  LiveSessionDetail,
  EntryPoint,
} from "./types";

const DEFAULT_EVENTS_HISTORY_LIMIT = 2000;
const MAX_EVENTS_HISTORY_LIMIT = 10000;

export type SessionEventsHistoryResponse = {
  events: AgentEvent[];
  session_id: string;
  total: number;
  returned: number;
  truncated: boolean;
  limit: number;
};

export type RevealSessionFolderResponse = {
  path: string;
  opened: boolean;
  launcher?: string;
  error?: string;
  hint?: string;
};

export type SessionFileEntry = {
  path: string;
  type: "file" | "dir";
  size: number | null;
  modified: number;
};

export type SessionFilesListResponse = {
  session_id: string;
  root: string;
  entries: SessionFileEntry[];
  total: number;
  returned: number;
  truncated: boolean;
  limit: number;
};

export type SessionFilePreviewResponse = {
  session_id: string;
  path: string;
  size: number;
  binary: boolean;
  encoding: string | null;
  content: string | null;
  truncated: boolean;
  preview_limit_bytes: number;
};

type SessionEventsHistoryRaw = Partial<SessionEventsHistoryResponse>;

function _resolveHistoryLimit(limit?: number): number {
  if (typeof limit !== "number" || !Number.isFinite(limit)) {
    return DEFAULT_EVENTS_HISTORY_LIMIT;
  }
  const rounded = Math.trunc(limit);
  return Math.max(1, Math.min(MAX_EVENTS_HISTORY_LIMIT, rounded));
}

export function normalizeSessionEventsHistoryResponse(
  sessionId: string,
  payload: SessionEventsHistoryRaw,
  requestedLimit?: number,
): SessionEventsHistoryResponse {
  const events = Array.isArray(payload.events) ? payload.events : [];
  const fallbackLimit = _resolveHistoryLimit(requestedLimit);
  const limit =
    typeof payload.limit === "number" && Number.isFinite(payload.limit)
      ? _resolveHistoryLimit(payload.limit)
      : fallbackLimit;

  const total =
    typeof payload.total === "number" && Number.isFinite(payload.total)
      ? Math.max(0, Math.trunc(payload.total))
      : events.length;

  const returnedRaw =
    typeof payload.returned === "number" && Number.isFinite(payload.returned)
      ? Math.max(0, Math.trunc(payload.returned))
      : events.length;
  const returned = Math.min(returnedRaw, events.length);

  const truncated =
    typeof payload.truncated === "boolean"
      ? payload.truncated
      : total > returned;

  return {
    events,
    session_id:
      typeof payload.session_id === "string" && payload.session_id.trim()
        ? payload.session_id
        : sessionId,
    total,
    returned,
    truncated,
    limit,
  };
}

export const sessionsApi = {
  // --- Session lifecycle ---

  /** Create a session. If agentPath is provided, loads a colony in one step. */
  create: (agentPath?: string, agentId?: string, model?: string, initialPrompt?: string, queenResumeFrom?: string, initialPhase?: string, workerName?: string) =>
    api.post<LiveSession>("/sessions", {
      agent_path: agentPath,
      agent_id: agentId,
      model,
      initial_prompt: initialPrompt,
      queen_resume_from: queenResumeFrom || undefined,
      initial_phase: initialPhase || undefined,
      worker_name: workerName || undefined,
    }),

  /** List all active sessions. */
  list: () => api.get<{ sessions: LiveSession[] }>("/sessions"),

  /** Get session detail (includes entry_points, colonies when a worker is loaded). */
  get: (sessionId: string) =>
    api.get<LiveSessionDetail>(`/sessions/${sessionId}`),

  /** Stop a session entirely. */
  stop: (sessionId: string) =>
    api.delete<{ session_id: string; stopped: boolean }>(
      `/sessions/${sessionId}`,
    ),

  // --- Colony lifecycle ---

  loadColony: (
    sessionId: string,
    agentPath: string,
    colonyId?: string,
    model?: string,
  ) =>
    api.post<LiveSession>(`/sessions/${sessionId}/colony`, {
      agent_path: agentPath,
      colony_id: colonyId,
      model,
    }),

  unloadColony: (sessionId: string) =>
    api.delete<{ session_id: string; colony_unloaded: boolean }>(
      `/sessions/${sessionId}/colony`,
    ),

  // --- Session info ---

  stats: (sessionId: string) =>
    api.get<Record<string, unknown>>(`/sessions/${sessionId}/stats`),

  entryPoints: (sessionId: string) =>
    api.get<{ entry_points: EntryPoint[] }>(
      `/sessions/${sessionId}/entry-points`,
    ),

  updateTrigger: (
    sessionId: string,
    triggerId: string,
    patch: { task?: string; trigger_config?: Record<string, unknown> },
  ) =>
    api.patch<{ trigger_id: string; task: string; trigger_config: Record<string, unknown> }>(
      `/sessions/${sessionId}/triggers/${triggerId}`,
      patch,
    ),

  activateTrigger: (sessionId: string, triggerId: string) =>
    api.post<{ status: string; trigger_id: string }>(
      `/sessions/${sessionId}/triggers/${triggerId}/activate`,
    ),

  deactivateTrigger: (sessionId: string, triggerId: string) =>
    api.post<{ status: string; trigger_id: string }>(
      `/sessions/${sessionId}/triggers/${triggerId}/deactivate`,
    ),

  runTrigger: (sessionId: string, triggerId: string) =>
    api.post<{ status: string; trigger_id: string }>(
      `/sessions/${sessionId}/triggers/${triggerId}/run`,
    ),

  colonies: (sessionId: string) =>
    api.get<{ colonies: string[] }>(`/sessions/${sessionId}/colonies`),

  /** Get persisted eventbus log for a session (works for cold sessions — used for full UI replay).
   *
   * Returns the TAIL of the event log. Default limit 2000 (server
   * clamps to [1, 10000]); older events get dropped and
   * ``truncated: true`` is set so the UI can show an indicator.
   */
  eventsHistory: async (sessionId: string, limit?: number) => {
    const payload = await api.get<SessionEventsHistoryRaw>(
      `/sessions/${sessionId}/events/history${
        limit ? `?limit=${limit}` : ""
      }`,
    );
    return normalizeSessionEventsHistoryResponse(sessionId, payload, limit);
  },

  /** Open the session's data folder in the OS file manager. */
  revealFolder: (sessionId: string) =>
    api.post<RevealSessionFolderResponse>(`/sessions/${sessionId}/reveal`),

  /** List session files (for in-browser data explorer). */
  files: (sessionId: string) =>
    api.get<SessionFilesListResponse>(`/sessions/${sessionId}/files`),

  /** Preview one file from session storage. */
  previewFile: (sessionId: string, path: string) =>
    api.get<SessionFilePreviewResponse>(
      `/sessions/${sessionId}/files/preview?path=${encodeURIComponent(path)}`,
    ),

  /** Build a direct download URL for a single session file. */
  fileDownloadUrl: (sessionId: string, path: string) =>
    `/api/sessions/${encodeURIComponent(sessionId)}/files/download?path=${encodeURIComponent(path)}`,

  /** List all queen sessions on disk — live + cold (post-restart). */
  history: () =>
    api.get<{ sessions: HistorySession[] }>("/sessions/history"),

  /** Permanently delete a history session (stops live session + removes disk files). */
  deleteHistory: (sessionId: string) =>
    api.delete<{ deleted: string }>(`/sessions/history/${sessionId}`),
};

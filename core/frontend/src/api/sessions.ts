import { api } from "./client";
import type {
  AgentEvent,
  LiveSession,
  LiveSessionDetail,
  EntryPoint,
} from "./types";

function parseFilenameFromDisposition(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const basicMatch = disposition.match(/filename=\"([^\"]+)\"|filename=([^;]+)/i);
  const value = basicMatch?.[1] || basicMatch?.[2];
  return value ? value.trim() : fallback;
}

async function parseApiError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { error?: string };
    if (body?.error) return body.error;
  } catch {
    // no-op
  }
  return fallback;
}

export const sessionsApi = {
  // --- Session lifecycle ---

  /** Create a session. If agentPath is provided, loads a graph in one step. */
  create: (
    agentPath?: string,
    agentId?: string,
    model?: string,
    initialPrompt?: string,
    queenResumeFrom?: string,
    projectId?: string,
  ) =>
    api.post<LiveSession>("/sessions", {
      agent_path: agentPath,
      agent_id: agentId,
      model,
      initial_prompt: initialPrompt,
      queen_resume_from: queenResumeFrom || undefined,
      project_id: projectId || undefined,
    }),

  /** List all active sessions. */
  list: (projectId?: string) =>
    api.get<{ sessions: LiveSession[] }>(
      `/sessions${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`,
    ),

  /** Get session detail (includes entry_points, graphs when a graph is loaded). */
  get: (sessionId: string) =>
    api.get<LiveSessionDetail>(`/sessions/${sessionId}`),

  /** Stop a session entirely. */
  stop: (sessionId: string) =>
    api.delete<{ session_id: string; stopped: boolean }>(
      `/sessions/${sessionId}`,
    ),

  // --- Graph lifecycle ---

  loadGraph: (
    sessionId: string,
    agentPath: string,
    graphId?: string,
    model?: string,
  ) =>
    api.post<LiveSession>(`/sessions/${sessionId}/graph`, {
      agent_path: agentPath,
      graph_id: graphId,
      model,
    }),

  unloadGraph: (sessionId: string) =>
    api.delete<{ session_id: string; graph_unloaded: boolean }>(
      `/sessions/${sessionId}/graph`,
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

  graphs: (sessionId: string) =>
    api.get<{ graphs: string[] }>(`/sessions/${sessionId}/graphs`),

  /** Get persisted eventbus log for a session (works for cold sessions — used for full UI replay). */
  eventsHistory: (sessionId: string) =>
    api.get<{ events: AgentEvent[]; session_id: string }>(`/sessions/${sessionId}/events/history`),

  /** Open the session's data folder in the OS file manager. */
  revealFolder: (sessionId: string) =>
    api.post<{ path: string; opened?: boolean; error?: string; hint?: string; launcher?: string }>(
      `/sessions/${sessionId}/reveal`,
    ),

  /** Download session data as a ZIP archive. */
  exportArchive: async (sessionId: string) => {
    const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/export`);
    if (!response.ok) {
      const fallback = `Failed to export session data (HTTP ${response.status})`;
      throw new Error(await parseApiError(response, fallback));
    }
    const fallbackName = `session-${sessionId}.zip`;
    const filename = parseFilenameFromDisposition(
      response.headers.get("Content-Disposition"),
      fallbackName,
    );
    const blob = await response.blob();
    return { blob, filename };
  },

  /** List all queen sessions on disk — live + cold (post-restart). */
  history: (projectId?: string) =>
    api.get<{ sessions: Array<{ session_id: string; cold: boolean; live: boolean; has_messages: boolean; created_at: number; agent_name?: string | null; agent_path?: string | null; project_id?: string | null }> }>(
      `/sessions/history${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`,
    ),

  /** Permanently delete a history session (stops live session + removes disk files). */
  deleteHistory: (sessionId: string) =>
    api.delete<{ deleted: string }>(`/sessions/history/${sessionId}`),
};

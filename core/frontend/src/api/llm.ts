import { api } from "./client";

export interface LlmSyncQueueStatus {
  limit: number;
  in_flight: number | null;
  available: number | null;
  queued: number | null;
}

export interface LlmAsyncLoopStatus {
  loop_id: number;
  in_flight: number;
  queued: number;
  available: number;
}

export interface LlmAsyncQueueStatus {
  limit_per_loop: number;
  loops: LlmAsyncLoopStatus[];
  total_in_flight: number;
  total_queued: number;
}

export interface LlmQueueSnapshot {
  limits: {
    global_concurrency: number;
    claude_concurrency: number;
  };
  backoff: {
    default_base_seconds: number;
    default_max_seconds: number;
    claude_base_seconds: number;
    claude_max_seconds: number;
  };
  sync: {
    global: LlmSyncQueueStatus;
    claude: LlmSyncQueueStatus;
  };
  async: {
    global: LlmAsyncQueueStatus;
    claude: LlmAsyncQueueStatus;
  };
}

export interface LlmQueueStatusResponse {
  status: string;
  queue: LlmQueueSnapshot;
}

export const llmApi = {
  queueStatus: () => api.get<LlmQueueStatusResponse>("/llm/queue/status"),
};

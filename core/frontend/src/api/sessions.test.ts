import { afterEach, describe, expect, it, vi } from "vitest";

import type { AgentEvent } from "./types";
import {
  normalizeSessionEventsHistoryResponse,
  sessionsApi,
} from "./sessions";

function makeEvent(idx: number): AgentEvent {
  return {
    type: "custom",
    stream_id: "default",
    node_id: null,
    execution_id: null,
    data: { idx },
    timestamp: `2026-04-23T00:00:0${idx}Z`,
    correlation_id: null,
    colony_id: null,
  };
}

describe("normalizeSessionEventsHistoryResponse", () => {
  it("fills missing metadata for backward-compatible payloads", () => {
    const payload = normalizeSessionEventsHistoryResponse("session_a", {
      events: [makeEvent(1)],
      session_id: "session_a",
    });

    expect(payload.total).toBe(1);
    expect(payload.returned).toBe(1);
    expect(payload.truncated).toBe(false);
    expect(payload.limit).toBe(2000);
  });

  it("preserves explicit server metadata", () => {
    const payload = normalizeSessionEventsHistoryResponse(
      "session_b",
      {
        events: [makeEvent(1), makeEvent(2)],
        session_id: "session_b",
        total: 12,
        returned: 2,
        truncated: true,
        limit: 2,
      },
      100,
    );

    expect(payload.total).toBe(12);
    expect(payload.returned).toBe(2);
    expect(payload.truncated).toBe(true);
    expect(payload.limit).toBe(2);
  });
});

describe("sessionsApi.eventsHistory", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("requests history endpoint with limit and returns normalized contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        events: [makeEvent(1)],
        session_id: "session_api",
      }),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const payload = await sessionsApi.eventsHistory("session_api", 50);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/sessions/session_api/events/history?limit=50",
    );
    expect(payload).toMatchObject({
      session_id: "session_api",
      total: 1,
      returned: 1,
      truncated: false,
      limit: 50,
    });
  });
});

describe("sessionsApi file explorer helpers", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("encodes file path for preview endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        session_id: "session_api",
        path: "logs/run log.txt",
        size: 12,
        binary: false,
        encoding: "utf-8",
        content: "hello",
        truncated: false,
        preview_limit_bytes: 262144,
      }),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await sessionsApi.previewFile("session_api", "logs/run log.txt");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/sessions/session_api/files/preview?path=logs%2Frun%20log.txt",
    );
  });

  it("builds encoded download URL", () => {
    const url = sessionsApi.fileDownloadUrl("session_api", "logs/run log.txt");
    expect(url).toBe(
      "/api/sessions/session_api/files/download?path=logs%2Frun%20log.txt",
    );
  });
});

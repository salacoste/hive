import { afterEach, describe, expect, it, vi } from "vitest";

import { opsApi } from "./ops";

describe("opsApi.releaseMatrix", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("reads release matrix snapshot from autonomous ops payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        release_matrix: {
          path: "/tmp/gate-latest.json",
          status: "pass",
          must_passed: 6,
          must_total: 6,
          must_failed: 0,
          must_missing: 0,
          generated_at: "2026-04-23T21:00:00Z",
        },
      }),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const snapshot = await opsApi.releaseMatrix();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/autonomous/ops/status");
    expect(snapshot).toMatchObject({
      status: "pass",
      must_passed: 6,
      must_total: 6,
      generated_at: "2026-04-23T21:00:00Z",
    });
  });

  it("falls back to summary fields when release_matrix object is absent", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        summary: {
          release_matrix_status: "fail",
          release_matrix_must_passed: 5,
          release_matrix_must_total: 6,
          release_matrix_must_failed: 1,
          release_matrix_must_missing: 0,
          release_matrix_generated_at: "2026-04-23T22:00:00Z",
        },
      }),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const snapshot = await opsApi.releaseMatrix();

    expect(snapshot).toMatchObject({
      status: "fail",
      must_passed: 5,
      must_total: 6,
      must_failed: 1,
      must_missing: 0,
      generated_at: "2026-04-23T22:00:00Z",
    });
  });
});


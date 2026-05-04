import { afterEach, describe, expect, it, vi } from "vitest";

import { autonomousApi } from "./autonomous";
import { ApiError } from "./client";

describe("autonomousApi intake contract", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("fetches intake template payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        required_fields: [
          "title",
          "goal",
          "acceptance_criteria",
          "constraints",
          "delivery_mode",
        ],
        delivery_mode_options: ["patch_and_pr", "patch_only", "pr_only"],
        example: {
          title: "Fix redirect downgrade",
          goal: "Keep POST method intact during redirect handling.",
          acceptance_criteria: ["Redirect regression test passes"],
          constraints: ["Container-first only"],
          delivery_mode: "patch_and_pr",
        },
      }),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const payload = await autonomousApi.intakeTemplate();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/autonomous/backlog/intake/template");
    expect(payload.required_fields).toContain("title");
    expect(payload.example.delivery_mode).toBe("patch_and_pr");
  });

  it("throws ApiError with actionable validation details on 400", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({
        valid: false,
        errors: ["goal is required"],
        hints: ["Use /api/autonomous/backlog/intake/template"],
      }),
      statusText: "Bad Request",
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await expect(
      autonomousApi.validateIntake({
        title: "Short",
      }),
    ).rejects.toBeInstanceOf(ApiError);
  });
});


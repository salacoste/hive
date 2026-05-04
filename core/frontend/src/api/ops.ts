import { api } from "./client";

export interface ReleaseMatrixSnapshot {
  path: string;
  status: "pass" | "fail" | "unknown";
  must_passed: number | null;
  must_total: number | null;
  must_failed: number | null;
  must_missing: number | null;
  generated_at: string | null;
}

interface AutonomousOpsStatusResponse {
  summary?: {
    release_matrix_status?: string | null;
    release_matrix_must_passed?: number | null;
    release_matrix_must_total?: number | null;
    release_matrix_must_failed?: number | null;
    release_matrix_must_missing?: number | null;
    release_matrix_generated_at?: string | null;
  };
  release_matrix?: Partial<ReleaseMatrixSnapshot>;
}

function normalizeStatus(raw: unknown): "pass" | "fail" | "unknown" {
  const text = String(raw ?? "").trim().toLowerCase();
  if (text === "pass" || text === "fail") return text;
  return "unknown";
}

function toNullableInt(raw: unknown): number | null {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return Math.trunc(raw);
  }
  if (typeof raw === "string" && raw.trim().length > 0) {
    const parsed = Number(raw);
    if (Number.isFinite(parsed)) return Math.trunc(parsed);
  }
  return null;
}

export const opsApi = {
  releaseMatrix: async (): Promise<ReleaseMatrixSnapshot> => {
    const payload = await api.get<AutonomousOpsStatusResponse>("/autonomous/ops/status");
    const matrix = payload.release_matrix ?? {};
    const summary = payload.summary ?? {};
    return {
      path: String(matrix.path ?? ""),
      status: normalizeStatus(matrix.status ?? summary.release_matrix_status),
      must_passed: toNullableInt(matrix.must_passed ?? summary.release_matrix_must_passed),
      must_total: toNullableInt(matrix.must_total ?? summary.release_matrix_must_total),
      must_failed: toNullableInt(matrix.must_failed ?? summary.release_matrix_must_failed),
      must_missing: toNullableInt(matrix.must_missing ?? summary.release_matrix_must_missing),
      generated_at: String(
        matrix.generated_at ?? summary.release_matrix_generated_at ?? "",
      ).trim() || null,
    };
  },
};


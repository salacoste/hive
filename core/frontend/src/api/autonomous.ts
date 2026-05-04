import { api } from "./client";

export interface BacklogIntakeTemplateResponse {
  required_fields: string[];
  delivery_mode_options: string[];
  example: {
    title: string;
    goal: string;
    acceptance_criteria: string[];
    constraints: string[];
    delivery_mode: string;
  };
}

export interface BacklogIntakeValidationSuccessResponse {
  valid: true;
  normalized: {
    title: string;
    goal: string;
    acceptance_criteria: string[];
    constraints: string[];
    delivery_mode: string;
  };
}

export interface BacklogIntakeValidationErrorResponse {
  valid?: false;
  errors?: string[];
  hints?: string[];
  error?: string;
}

export const autonomousApi = {
  intakeTemplate: () =>
    api.get<BacklogIntakeTemplateResponse>("/autonomous/backlog/intake/template"),

  validateIntake: (payload: Record<string, unknown>) =>
    api.post<BacklogIntakeValidationSuccessResponse>(
      "/autonomous/backlog/intake/validate",
      payload,
    ),
};


/*
 * Every call to the backend goes through this file.
 * Errors always arrive as ApiError with a message that can be shown to the user.
 */
import type { AnalysisJob, ExampleSequence, HealthResponse } from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const OFFLINE_MESSAGE = "Cannot reach the analysis server. Make sure the backend is running.";

function messageFrom(payload: unknown, status: number, rawText: string): string {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string" && detail.trim() !== "") {
      return detail;
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item: unknown) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : "",
        )
        .filter((text) => text !== "");
      if (messages.length > 0) {
        return messages.join(" ");
      }
    }
  }
  // The development proxy answers with an empty 5xx when FastAPI is not running.
  if (status >= 500 && rawText.trim() === "") {
    return OFFLINE_MESSAGE;
  }
  if (status >= 500) {
    return `The analysis server ran into a problem (HTTP ${status}).`;
  }
  return `The request failed (HTTP ${status}).`;
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }
    throw new ApiError(OFFLINE_MESSAGE, 0);
  }

  const rawText = await response.text();
  let payload: unknown = null;
  if (rawText !== "") {
    try {
      payload = JSON.parse(rawText);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    throw new ApiError(messageFrom(payload, response.status, rawText), response.status);
  }
  return payload as T;
}

function jobPath(jobId: string): string {
  return `/api/analyses/${encodeURIComponent(jobId)}`;
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>("/api/health", { signal }),

  examples: (signal?: AbortSignal) => request<ExampleSequence[]>("/api/examples", { signal }),

  createAnalysis: (sequence: string, name: string) =>
    request<AnalysisJob>("/api/analyses", {
      method: "POST",
      body: { sequence, name: name.trim() === "" ? null : name.trim() },
    }),

  getAnalysis: (jobId: string, signal?: AbortSignal) =>
    request<AnalysisJob>(jobPath(jobId), { signal }),

  cancelAnalysis: (jobId: string) => request<AnalysisJob>(`${jobPath(jobId)}/cancel`, { method: "POST" }),
};

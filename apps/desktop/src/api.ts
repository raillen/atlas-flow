/** Typed client for the Atlas Flow backend (docs/03-implementation/API_CONTRACTS.md). */

const BASE_URL = import.meta.env.VITE_ATLAS_API ?? "http://localhost:8000";

export interface GoalView {
  id: string;
  phase: string;
  title: string;
  state: string;
  objective: string;
  acceptance: string[];
  gates: Record<string, string>;
  dependencies: string[];
  evidenceCount: number;
}

export interface TaskView {
  id: string;
  objective: string;
  state: string;
  role: string | null;
  risk: string;
  scope: string[];
  dependencies: string[];
}

export interface AttemptView {
  id: string;
  taskId: string;
  runner: string | null;
  modelId: string | null;
  state: string;
  startedAt: string | null;
  completedAt: string | null;
  errorMsg: string | null;
}

export interface EventView {
  id: string;
  timestamp: string;
  type: string;
  runId: string | null;
  payload: Record<string, unknown>;
}

export interface EvidenceView {
  id: string;
  gate: string;
  kind: string;
  verdict: string;
  uri: string;
  taskId: string | null;
  attachedAt: string;
}

export interface RunView {
  id: string;
  goalId: string;
  goalRevision: string;
  state: string;
  autonomy: string;
  createdAt: string;
  taskCount: number;
}

export interface RunDetail {
  run: RunView;
  tasks: TaskView[];
  attempts: AttemptView[];
  events: EventView[];
}

export interface GateView {
  gate: string;
  requirement: string;
  verdict: string;
  evidenceIds: string[];
  details: string;
}

export interface GoalVerification {
  goalId: string;
  gates: GateView[];
  evidence: EvidenceView[];
  completable: boolean;
  blocking: string;
}

export interface DocEntry {
  path: string;
  title: string;
  section: string;
}

export interface ProjectInfo {
  id: string;
  types: string[];
  phases: number;
  agents: string[];
  skills: string[];
  runners: string[];
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * The backend serializes snake_case; the UI reads camelCase. Converting at the
 * boundary keeps the naming convention of each side intact instead of leaking
 * Python field names through every component.
 */
function toCamel(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(toCamel);
  if (value === null || typeof value !== "object") return value;

  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, entry]) => [
      key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase()),
      // Event payloads are opaque pass-through data: renaming their keys would
      // corrupt values the backend expects to round-trip unchanged.
      key === "payload" || key === "gates" ? entry : toCamel(entry),
    ]),
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(response.status, detail);
  }

  return toCamel(await response.json()) as T;
}

export const api = {
  project: () => request<ProjectInfo>("/api/project"),
  goals: () => request<GoalView[]>("/api/goals"),
  goal: (id: string) => request<GoalView>(`/api/goals/${id}`),
  verification: (id: string) =>
    request<GoalVerification>(`/api/goals/${id}/verification`),
  runs: () => request<RunView[]>("/api/runs"),
  run: (id: string) => request<RunDetail>(`/api/runs/${id}`),
  startRun: (goalId: string, runner: string) =>
    request<RunView>("/api/runs", {
      method: "POST",
      body: JSON.stringify({ goal_id: goalId, runner }),
    }),
  docs: () => request<DocEntry[]>("/api/docs"),
  doc: (path: string) =>
    request<{ path: string; content: string }>(`/api/docs/${path}`),
};

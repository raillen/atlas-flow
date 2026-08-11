/** Typed client for the Atlas Flow backend (docs/03-implementation/API_CONTRACTS.md). */

import { desktop } from "./desktop";

/**
 * Where the backend is, which the shell decides at runtime.
 *
 * It used to be baked in at build time, so a packaged app whose shell started
 * a backend on any other port showed "Could not reach the backend" forever
 * while a healthy backend sat there answering. The build-time value survives
 * as the fallback for a browser, where there is no shell to ask.
 *
 * The shell is asked on the first request rather than at startup: the Tauri
 * bridge is not on `globalThis` yet while this module is being evaluated, so
 * asking then answered null and left every request pointed at the wrong port
 * for the life of the window. An unanswered question is not cached — the next
 * request asks again.
 */
const FALLBACK_URL = import.meta.env.VITE_ATLAS_API ?? "http://localhost:8000";
let baseUrl = FALLBACK_URL;
let asked = false;

export async function resolveBaseUrl(): Promise<string> {
  if (asked) return baseUrl;
  const status = await desktop.backendStatus();
  if (status === null) return baseUrl; // a browser: nothing to ask, ask again later
  baseUrl = status.url.replace(/\/+$/, "");
  asked = true;
  return baseUrl;
}

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
  projectId: string;
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

export interface PlanTaskView {
  id: string;
  objective: string;
  dependencies: string[];
  writeScope: string[];
  gates: string[];
  risk: string;
  parallelizable: boolean;
  capabilities: string[];
}

export interface PlanView {
  id: string;
  projectId: string;
  goalId: string;
  goalRevision: string;
  state: string;
  autonomy: string;
  runner: string;
  integrationTarget: string;
  createdAt: string;
  tasks: PlanTaskView[];
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

export interface RoleRouteView {
  role: string;
  selected: string | null;
  provider: string | null;
  explanation: string;
  fallbackAttempts: number;
}

export interface ModelStatsView {
  modelKey: string;
  uses: number;
  successes: number;
  failures: number;
  successRate: number;
  averageLatencyMs: number;
}

/** `state` is "pending" until the live registry answers, then reachable/degraded. */
export interface RoutingView {
  state: string;
  reachable: boolean;
  degraded: boolean;
  reason: string;
  probedAt: string;
  available: string[];
  roles: RoleRouteView[];
  stats: ModelStatsView[];
}

export interface RouteDecisionView {
  taskId: string;
  role: string;
  selected: string | null;
  candidates: string[];
  reason: string;
  fallbackAttempts: number;
}

export interface DiscussMessage {
  id: string;
  timestamp: string;
  content: string;
  turnType: string;
  references: MessageReference[];
}

export type MessageReferenceKind = "file" | "image";

export interface MessageReference {
  path: string;
  kind: MessageReferenceKind;
  label: string;
  mimeType: string | null;
}

export interface DecisionCandidate {
  id: string;
  title: string;
  statement: string;
  rationale: string;
  status: string;
  affectedDomains: string[];
  requiresAdr: boolean;
  timestamp: string;
}

/** How complete each domain of the Project Draft is. */
export type Completeness = "unknown" | "partial" | "sufficient";

export interface ProjectDraft {
  product: Completeness;
  architecture: Completeness;
  ux: Completeness;
  data: Completeness;
  security: Completeness;
  quality: Completeness;
  operations: Completeness;
  aiOrchestration: Completeness;
  roadmap: Completeness;
}

export interface DiscussionSession {
  id: string;
  projectId: string;
  title: string;
  messages: DiscussMessage[];
  decisions: DecisionCandidate[];
  draft: ProjectDraft;
  startedAt: string;
}

export interface DocEntry {
  path: string;
  title: string;
  section: string;
}

export type ProjectMode =
  | "atlas-ready"
  | "atlas-needs-adaptation"
  | "atlas-incompatible"
  | "external";

export interface ProjectCapabilities {
  canExplore: boolean;
  canDiscuss: boolean;
  canAdapt: boolean;
  canPlan: boolean;
  canRun: boolean;
  canReview: boolean;
}

export interface ProjectInspection {
  root: string;
  mode: ProjectMode;
  projectId: string;
  projectName: string;
  types: string[];
  frameworkName: string | null;
  frameworkVersion: string | null;
  frameworkSupported: boolean;
  gitPresent: boolean;
  missingManifests: string[];
  invalidManifests: string[];
  reason: string;
  recommendation: string;
  capabilities: ProjectCapabilities;
}

export interface ProjectInfo {
  id: string;
  name?: string;
  types: string[];
  phases: number;
  agents: string[];
  skills: string[];
  runners: string[];
  mode?: ProjectMode;
  reason?: string;
  recommendation?: string;
}

export interface ProjectFileView {
  path: string;
  kind: "text" | "binary";
  size: number;
}

export interface ProjectFileContent {
  path: string;
  content: string;
  truncated: boolean;
}

export interface AdaptationFileView {
  path: string;
  action: "create" | "conflict";
  reason: string;
}

export interface AdaptationPreview {
  ready: boolean;
  files: AdaptationFileView[];
  conflicts: string[];
  limitations: string[];
}

export interface AdaptationApplyResult {
  written: string[];
  inspection: ProjectInspection;
}

export interface ConfigSourceView {
  value: string;
  scope: string;
  environmentVariable: string | null;
}

export interface SettingView {
  key: string;
  value: unknown;
  default: unknown;
  source: ConfigSourceView;
  restartRequired: boolean;
  appliesTo: string;
  description: string;
  kind: string;
}

export interface ProviderView {
  key: string;
  provider: string;
  commandCodeId: string;
  priority: string;
  availability: string;
  credentialRef: string | null;
  credentialConfigured: boolean;
}

export interface SettingsDocument {
  settings: SettingView[];
  providers: ProviderView[];
  mcp: { enabled: boolean; servers: unknown[]; skipped: Record<string, unknown> };
  diagnostics: Record<string, unknown>;
  restartRequired: boolean;
  restartReason: string | null;
}

export interface SettingsSaveResult extends SettingsDocument {
  changed: string[];
  writtenPaths: string[];
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
  const response = await fetch(`${await resolveBaseUrl()}${path}`, {
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
  inspection: () => request<ProjectInspection>("/api/project/inspection"),
  projectFiles: () => request<ProjectFileView[]>("/api/project/files"),
  projectFile: (path: string) =>
    request<ProjectFileContent>(`/api/project/files/${path.split("/").map(encodeURIComponent).join("/")}`),
  adaptationPreview: () =>
    request<AdaptationPreview>("/api/project/adaptation/preview", { method: "POST" }),
  applyAdaptation: (paths: string[]) =>
    request<AdaptationApplyResult>("/api/project/adaptation/apply", {
      method: "POST",
      body: JSON.stringify({ paths }),
    }),
  goals: () => request<GoalView[]>("/api/goals"),
  goal: (id: string) => request<GoalView>(`/api/goals/${id}`),
  verification: (id: string) =>
    request<GoalVerification>(`/api/goals/${id}/verification`),
  runs: () => request<RunView[]>("/api/runs"),
  run: (id: string) => request<RunDetail>(`/api/runs/${id}`),
  createPlan: (goalId: string, runner = "dummy", autonomy = "agentic") =>
    request<PlanView>(`/api/goals/${goalId}/plans`, {
      method: "POST",
      body: JSON.stringify({ runner, autonomy }),
    }),
  plans: (goalId: string) =>
    request<PlanView[]>(`/api/goals/${goalId}/plans`),
  plan: (id: string) => request<PlanView>(`/api/plans/${id}`),
  lockPlan: (id: string) =>
    request<PlanView>(`/api/plans/${id}/lock`, { method: "POST" }),
  startRun: (goalId: string, runner: string, planId?: string) =>
    request<RunView>("/api/runs", {
      method: "POST",
      body: JSON.stringify({ goal_id: goalId, runner, plan_id: planId }),
    }),
  cancelRun: (id: string) =>
    request<RunView>(`/api/runs/${id}/cancel`, { method: "POST" }),
  routing: () => request<RoutingView>("/api/routing"),
  runRouting: (id: string) =>
    request<RouteDecisionView[]>(`/api/runs/${id}/routing`),
  discussions: () => request<string[]>("/api/discussions"),
  createDiscussion: () =>
    request<{ sessionId: string }>("/api/discussions", { method: "POST" }),
  discussion: (id: string) =>
    request<DiscussionSession>(`/api/discussions/${id}`),
  sendMessage: (id: string, content: string, references: MessageReference[] = []) =>
    request<DiscussMessage>(`/api/discussions/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, turn_type: "message", references }),
    }),
  proposeDecision: (id: string, title: string, statement: string) =>
    request<DecisionCandidate>(`/api/discussions/${id}/decisions`, {
      method: "POST",
      body: JSON.stringify({ title, statement, rationale: "" }),
    }),
  acceptDecision: (id: string, decisionId: string) =>
    request<DecisionCandidate>(
      `/api/discussions/${id}/decisions/${decisionId}/accept`,
      { method: "POST" },
    ),
  docs: () => request<DocEntry[]>("/api/docs"),
  doc: (path: string) =>
    request<{ path: string; content: string }>(`/api/docs/${path}`),
  settings: () => request<SettingsDocument>("/api/settings"),
  validateSettings: (scope: string, values: Record<string, unknown>) =>
    request<SettingsDocument>("/api/settings/validate", {
      method: "POST",
      body: JSON.stringify({ scope, values }),
    }),
  saveSettings: (scope: string, values: Record<string, unknown>) =>
    request<SettingsSaveResult>("/api/settings", {
      method: "PUT",
      body: JSON.stringify({ scope, values }),
    }),
  resetSettings: (scope: string, keys: string[]) =>
    request<SettingsDocument>("/api/settings/reset", {
      method: "POST",
      body: JSON.stringify({ scope, keys }),
    }),
};

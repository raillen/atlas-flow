/** Canonical and operational domain types (docs/01-architecture/DOMAIN_MODEL.md). */

export type GoalState = "PLANNED" | "READY" | "ACTIVE" | "BLOCKED" | "DONE" | "CANCELLED";

export type GateRequirement = "required" | "optional";

export interface GoalGates {
  build: GateRequirement;
  tests: GateRequirement;
  review: GateRequirement;
  documentation: GateRequirement;
}

export interface Goal {
  id: string;
  phase: string;
  title: string;
  state: GoalState;
  objective: string;
  constraints: string[];
  acceptance: string[];
  dependencies: string[];
  gates: GoalGates;
}

export type RunState = "PENDING" | "RUNNING" | "PAUSED" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface Run {
  id: string;
  goalId: string;
  goalRevision: string;
  state: RunState;
  startedAt: string;
}

export type TaskState = "PENDING" | "READY" | "RUNNING" | "SUCCEEDED" | "FAILED" | "SKIPPED";

export interface Task {
  id: string;
  runId: string;
  title: string;
  state: TaskState;
  writeScope: string[];
  gates: string[];
}

export interface Evidence {
  id: string;
  taskId: string;
  kind: string;
  uri?: string;
  hash?: string;
  attachedAt: string;
}

export interface ModelRoute {
  role: string;
  provider: string;
  modelId: string;
  fallbacks: string[];
}

export interface Runner {
  id: string;
  kind: string;
  capabilities: string[];
}

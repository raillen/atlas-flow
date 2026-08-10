/** AG-UI client primitives (docs/01-architecture/AG_UI_INTEGRATION.md, EVENT_MODEL.md). */

export const ATLAS_EVENT_NAMESPACES = [
  "atlas.goal",
  "atlas.task",
  "atlas.runner",
  "atlas.evidence",
  "atlas.routing",
] as const;

export type AtlasEventNamespace = (typeof ATLAS_EVENT_NAMESPACES)[number];

export interface DomainEvent<TPayload = unknown> {
  id: string;
  timestamp: string;
  projectId: string;
  runId?: string;
  type: string;
  version: number;
  payload: TPayload;
}

export function isAtlasEventType(type: string): boolean {
  return ATLAS_EVENT_NAMESPACES.some((ns) => type === ns || type.startsWith(`${ns}.`));
}

export function createDomainEvent<TPayload>(
  type: string,
  projectId: string,
  payload: TPayload,
  runId?: string,
): DomainEvent<TPayload> {
  if (!isAtlasEventType(type)) {
    throw new Error(`Event type must be namespaced: ${type}`);
  }
  return {
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    projectId,
    runId,
    type,
    version: 1,
    payload,
  };
}

/** AG-UI client primitives (docs/01-architecture/AG_UI_INTEGRATION.md, EVENT_MODEL.md). */

/**
 * Every namespace the backend actually emits. Durable run history uses the
 * first group; the second is agent narration, which is broadcast live and
 * never persisted (see backend/atlas_flow/api/websocket.py).
 */
export const ATLAS_EVENT_NAMESPACES = [
  "atlas.run",
  "atlas.task",
  "atlas.attempt",
  "atlas.gate",
  "atlas.state",
  "atlas.agent",
  "atlas.terminal",
  "atlas.file",
  "atlas.tool",
  "atlas.plan",
  "atlas.discuss",
  "atlas.decision",
  "atlas.error",
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

export interface AgUiMessage {
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
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

export class AgUiClient {
  private ws: WebSocket | null = null;
  private _onMessage: ((msg: AgUiMessage) => void) | null = null;
  private _onStatus: ((connected: boolean) => void) | null = null;

  get connected() {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  connect(sessionId: string, serverUrl: string) {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    const ws = new WebSocket(`${serverUrl}/ws/${sessionId}`);
    this.ws = ws;
    ws.onopen = () => this._onStatus?.(true);
    ws.onclose = () => this._onStatus?.(false);
    ws.onerror = () => ws.close();
    ws.onmessage = (e) => {
      try {
        const msg: AgUiMessage = JSON.parse(e.data as string);
        this._onMessage?.(msg);
      } catch { /* ignore */ }
    };
  }

  disconnect() {
    this.ws?.close();
    this.ws = null;
  }

  onMessage(fn: (msg: AgUiMessage) => void) { this._onMessage = fn; }
  onStatus(fn: (connected: boolean) => void) { this._onStatus = fn; }

  send(message: Record<string, unknown>) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }
}

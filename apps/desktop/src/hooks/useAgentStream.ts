import { useEffect, useState } from "react";
import { AgUiClient, type AgUiMessage } from "@atlas-flow/ag-ui-client";

const WS_URL =
  (import.meta.env.VITE_ATLAS_API ?? "http://localhost:8000").replace(/^http/, "ws");

/** One thing the agent said, ran or changed, as it arrives over AG-UI. */
export interface AgentActivity {
  key: string;
  type: string;
  taskId: string;
  text: string;
  paths: string[];
  tool: string;
  status: string;
}

/** Narration event names, as broadcast by backend/atlas_flow/api/websocket.py. */
const NARRATION = new Set([
  "atlas.agent.message",
  "atlas.agent.thought",
  "atlas.terminal.output",
  "atlas.file.changed",
  "atlas.tool.call",
  "atlas.plan.updated",
]);

export function toActivity(message: AgUiMessage, index: number): AgentActivity | null {
  if (!NARRATION.has(message.type)) return null;
  const payload = message.payload ?? {};
  return {
    key: `${message.timestamp}-${index}`,
    type: message.type,
    taskId: String(payload.task_id ?? ""),
    text: String(payload.text ?? ""),
    paths: Array.isArray(payload.paths) ? payload.paths.map(String) : [],
    tool: String(payload.tool ?? ""),
    status: String(payload.status ?? ""),
  };
}

/**
 * Subscribes to agent narration for as long as `active` is true.
 *
 * These events are broadcast, not stored, so anything that arrives before the
 * socket opens is gone. That is the trade the backend makes deliberately: the
 * durable record of a run is its event log, and this is the live view on top.
 */
export function useAgentStream(sessionId: string, active: boolean, limit = 200) {
  const [activity, setActivity] = useState<AgentActivity[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!active) {
      setConnected(false);
      return;
    }

    let counter = 0;
    const client = new AgUiClient();
    client.onStatus(setConnected);
    client.onMessage((message) => {
      const entry = toActivity(message, counter++);
      if (entry === null) return;
      setActivity((current) => [...current, entry].slice(-limit));
    });
    client.connect(sessionId, WS_URL);

    return () => {
      client.disconnect();
      setConnected(false);
    };
  }, [sessionId, active, limit]);

  return { activity, connected };
}

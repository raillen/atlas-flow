import { useCallback, useEffect, useRef, useState } from "react";
import { AgUiClient, type AgUiMessage } from "@atlas-flow/ag-ui-client";
import { AtlasLogo } from "@atlas-flow/ui";

interface Props {
  sessionId: string;
  serverUrl: string;
}

const containerStyle: React.CSSProperties = {
  fontFamily: "system-ui, sans-serif",
  maxWidth: 800,
  margin: "0 auto",
  padding: "1rem",
  height: "100dvh",
  display: "flex",
  flexDirection: "column",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.5rem",
  paddingBottom: "0.75rem",
  borderBottom: "1px solid #e2e8f0",
  marginBottom: "0.5rem",
};

const statusStyle = (connected: boolean): React.CSSProperties => ({
  fontSize: "0.75rem",
  color: connected ? "#059669" : "#dc2626",
  marginLeft: "auto",
});

const feedStyle: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
  padding: "0.5rem 0",
  display: "flex",
  flexDirection: "column",
  gap: "0.25rem",
};

const eventStyle: React.CSSProperties = {
  padding: "0.25rem 0.5rem",
  fontSize: "0.85rem",
  borderBottom: "1px solid #f1f5f9",
};

const inputRowStyle: React.CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  paddingTop: "0.5rem",
};

const inputStyle: React.CSSProperties = {
  flex: 1,
  padding: "0.5rem",
  border: "1px solid #cbd5e1",
  borderRadius: "6px",
  fontSize: "0.9rem",
};

const buttonStyle: React.CSSProperties = {
  padding: "0.5rem 1rem",
  border: "none",
  borderRadius: "6px",
  background: "#6366f1",
  color: "white",
  cursor: "pointer",
  fontWeight: 500,
};

const eventLabel: Record<string, string> = {
  "atlas.discuss.message": "💬",
  "atlas.decision.proposed": "📋",
};

export function DiscussScreen({ sessionId, serverUrl }: Props) {
  const clientRef = useRef(new AgUiClient());
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<AgUiMessage[]>([]);
  const [input, setInput] = useState("");

  const client = clientRef.current;

  useEffect(() => {
    client.onStatus(setConnected);
    client.onMessage((msg) => setEvents((prev) => [...prev.slice(-199), msg]));
    client.connect(sessionId, serverUrl);

    const reconnectTimer = setInterval(() => {
      if (!client.connected) client.connect(sessionId, serverUrl);
    }, 3000);

    return () => {
      clearInterval(reconnectTimer);
      client.disconnect();
    };
  }, [sessionId, serverUrl, client]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text) return;
    client.send({ kind: "message", content: text });
    setInput("");
  }, [input, client]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const proposeDecision = useCallback(() => {
    const text = input.trim();
    if (!text) return;
    client.send({
      kind: "decision_propose",
      data: { title: text, statement: text, rationale: "", status: "PROPOSED" },
    });
    setInput("");
  }, [input, client]);

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <AtlasLogo size={28} />
        <strong>Atlas Flow — Discuss</strong>
        <span style={statusStyle(connected)}>
          {connected ? "● connected" : "○ disconnected"}
        </span>
      </div>

      <div style={feedStyle} role="log" aria-live="polite" aria-label="Discussion messages">
        {events.length === 0 && (
          <div style={{ color: "#94a3b8", fontStyle: "italic", padding: "0.5rem" }}>
            No messages yet. Start the conversation.
          </div>
        )}
        {events.map((evt, i) => (
          <div key={i} style={eventStyle}>
            <span style={{ marginRight: "0.5rem" }} aria-hidden="true">
              {eventLabel[evt.type] ?? "●"}
            </span>
            <span style={{ color: "#64748b", fontSize: "0.75rem" }}>
              {evt.type}
            </span>{" "}
            {typeof evt.payload.content === "string" && evt.payload.content}
            {typeof evt.payload.title === "string" && (
              <strong>{evt.payload.title}</strong>
            )}
          </div>
        ))}
      </div>

      <div style={inputRowStyle}>
        <label htmlFor="discuss-input" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden" }}>
          Type a message
        </label>
        <input
          id="discuss-input"
          style={inputStyle}
          placeholder="Type a message or decision..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          aria-label="Message input"
        />
        <button style={buttonStyle} onClick={handleSend}>
          Send
        </button>
        <button
          style={{ ...buttonStyle, background: "#0ea5e9" }}
          onClick={proposeDecision}
          title="Propose decision"
        >
          Decide
        </button>
      </div>
    </div>
  );
}

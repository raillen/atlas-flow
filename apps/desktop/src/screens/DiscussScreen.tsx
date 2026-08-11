import type { FC } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { AgUiClient, type AgUiMessage } from "@atlas-flow/ag-ui-client";
import {
  api,
  resolveBaseUrl,
  type DecisionCandidate,
  type DiscussionSession,
  type ProjectDraft,
} from "../api";
import { useAsync } from "../hooks/useAsync";
import {
  AsyncPanel,
  buttonStyle,
  card,
  muted,
  screen,
  SectionHeading,
  StatusBadge,
} from "../components/Primitives";
import { accent, surface, text, tone } from "../theme";

/** The socket lives wherever the backend does, which only the shell knows. */
async function socketUrl(): Promise<string> {
  return (await resolveBaseUrl()).replace(/^http/, "ws");
}

/** The nine domains a Project Draft tracks, in the order the Goal system lists them. */
export const DRAFT_DOMAINS: (keyof ProjectDraft)[] = [
  "product",
  "architecture",
  "ux",
  "data",
  "security",
  "quality",
  "operations",
  "aiOrchestration",
  "roadmap",
];

/**
 * How close a draft is to being finalizable, as a plain sentence.
 *
 * Finalization writes ADRs into `docs/`, and the backend refuses while any
 * domain is still short. Saying which ones is the difference between a button
 * that looks broken and one that explains itself.
 */
export function describeDraft(draft: ProjectDraft | undefined): string {
  if (draft === undefined) return "No draft yet.";
  const missing = DRAFT_DOMAINS.filter((domain) => draft[domain] !== "sufficient");
  if (missing.length === 0) return "Every domain is sufficient; the draft can be finalized.";
  return `${missing.length} of ${DRAFT_DOMAINS.length} domains still need work: ${missing.join(", ")}`;
}

export const DiscussScreen: FC = () => {
  const sessions = useAsync(() => api.discussions(), []);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [draftText, setDraftText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [live, setLive] = useState<AgUiMessage[]>([]);
  const feedRef = useRef<HTMLDivElement | null>(null);

  const session = useAsync(
    async () => (sessionId ? await api.discussion(sessionId) : null),
    [sessionId, reload],
  );

  // Pick up whichever session exists, rather than opening a new one on every
  // visit: a discussion nobody can find again is a discussion nobody keeps.
  useEffect(() => {
    if (sessionId === null && sessions.data && sessions.data.length > 0) {
      setSessionId(sessions.data[0]);
    }
  }, [sessions.data, sessionId]);

  useEffect(() => {
    if (sessionId === null) return;
    const client = new AgUiClient();
    client.onStatus(setConnected);
    client.onMessage((message) => setLive((current) => [...current, message]));
    // Connecting waits for the address, so a socket opened before the first
    // request cannot quietly attach to the wrong port.
    let dropped = false;
    void socketUrl().then((url) => {
      if (!dropped) client.connect(sessionId, url);
    });
    return () => {
      dropped = true;
      client.disconnect();
      setConnected(false);
    };
  }, [sessionId]);

  useEffect(() => {
    // Assigning scrollTop rather than calling scrollTo: the method is
    // absent in some environments, and a chat that throws while trying to
    // scroll is worse than one that does not scroll.
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [session.data, live]);

  const act = useCallback(async (work: () => Promise<unknown>) => {
    try {
      await work();
      setError(null);
      setReload((value) => value + 1);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, []);

  const start = () =>
    void act(async () => {
      const created = await api.createDiscussion();
      setSessionId(created.sessionId);
      sessions.reload();
    });

  const send = () => {
    const content = draftText.trim();
    if (!content || sessionId === null) return;
    setDraftText("");
    void act(() => api.sendMessage(sessionId, content));
  };

  const propose = () => {
    const content = draftText.trim();
    if (!content || sessionId === null) return;
    setDraftText("");
    void act(() => api.proposeDecision(sessionId, content, content));
  };

  return (
    <div style={screen}>
      <SectionHeading
        actions={
          <button type="button" style={buttonStyle} onClick={start}>
            New discussion
          </button>
        }
      >
        Discuss
      </SectionHeading>
      <p style={muted}>
        Conversation is stored, not just streamed. Decisions accepted here become
        ADRs and Decision Ledger entries in <code>docs/</code>.
      </p>

      <AsyncPanel
        loading={sessions.loading}
        error={sessions.error}
        onRetry={sessions.reload}
        isEmpty={sessionId === null && (sessions.data?.length ?? 0) === 0}
        emptyMessage="No discussions yet. Start one to begin."
      >
        {sessionId !== null && (
          <AsyncPanel
            loading={session.loading && !session.data}
            error={session.error}
            onRetry={session.reload}
          >
            {session.data && (
              <DiscussionBody
                session={session.data}
                connected={connected}
                feedRef={feedRef}
                onAccept={(decisionId) =>
                  void act(() => api.acceptDecision(session.data!.id, decisionId))
                }
              />
            )}
          </AsyncPanel>
        )}
      </AsyncPanel>

      {error && (
        <p style={{ ...muted, color: text.danger }} role="alert">
          {error}
        </p>
      )}

      {sessionId !== null && (
        <div style={{ display: "flex", gap: "0.4rem" }}>
          <input
            aria-label="Message"
            value={draftText}
            placeholder="Say something, or describe a decision"
            onChange={(event) => setDraftText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                send();
              }
            }}
            style={{
              flex: 1,
              padding: "0.5rem 0.7rem",
              borderRadius: 6,
              border: `1px solid ${tone.neutral.border}`,
              background: surface.card,
              color: text.primary,
              font: "inherit",
            }}
          />
          <button
            type="button"
            style={{ ...buttonStyle, background: accent.base, color: accent.on }}
            onClick={send}
          >
            Send
          </button>
          <button type="button" style={buttonStyle} onClick={propose}>
            Propose decision
          </button>
        </div>
      )}
    </div>
  );
};

const DiscussionBody: FC<{
  session: DiscussionSession;
  connected: boolean;
  feedRef: React.RefObject<HTMLDivElement | null>;
  onAccept: (decisionId: string) => void;
}> = ({ session, connected, feedRef, onAccept }) => (
  <>
    <div style={card}>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
        <strong>{session.title || session.id}</strong>
        <StatusBadge value={connected ? "RUNNING" : "PLANNED"} />
        <span style={muted}>{connected ? "live" : "not streaming"}</span>
      </div>
      <p style={{ ...muted, margin: "0.25rem 0 0" }}>{describeDraft(session.draft)}</p>
    </div>

    <section>
      <SectionHeading>Conversation</SectionHeading>
      <div
        ref={feedRef}
        role="log"
        aria-live="polite"
        aria-label="Discussion messages"
        style={{
          ...card,
          maxHeight: 320,
          overflowY: "auto",
          display: "grid",
          gap: "0.5rem",
        }}
      >
        {session.messages.length === 0 ? (
          <p style={muted}>Nothing said yet.</p>
        ) : (
          session.messages.map((message) => (
            <div key={message.id}>
              <span style={{ ...muted, marginRight: "0.5rem" }}>
                {message.timestamp.slice(11, 19)}
              </span>
              {message.content}
            </div>
          ))
        )}
      </div>
    </section>

    <section>
      <SectionHeading>Decisions</SectionHeading>
      {session.decisions.length === 0 ? (
        <p style={muted}>No decisions proposed yet.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.4rem" }}>
          {session.decisions.map((decision) => (
            <li key={decision.id} style={card}>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <StatusBadge value={decision.status.toUpperCase()} />
                <strong>{decision.title}</strong>
                {decision.requiresAdr && <span style={muted}>needs an ADR</span>}
                {isPending(decision) && (
                  <button
                    type="button"
                    style={{ ...buttonStyle, marginLeft: "auto" }}
                    onClick={() => onAccept(decision.id)}
                  >
                    Accept
                  </button>
                )}
              </div>
              <p style={{ ...muted, margin: "0.25rem 0 0" }}>{decision.statement}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  </>
);

/** Only a proposal can be accepted; anything else already has an answer. */
export function isPending(decision: DecisionCandidate): boolean {
  return decision.status.toUpperCase() === "PROPOSED";
}

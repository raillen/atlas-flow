import type { FC } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { accent, space, surface, text, tone, type } from "../theme";
import { helpText, parseCommand } from "./commands";

/** One thing in the transcript. Actions are the chat's own answers. */
export interface Turn {
  id: string;
  author: "you" | "atlas";
  text: string;
  /** Something to click, when the answer produced one. */
  action?: { label: string; goalId?: string; runId?: string };
  failed?: boolean;
}

let counter = 0;
const nextId = () => `turn-${++counter}`;

export interface ChatStageProps {
  sessionId: string | null;
  goalIds: string[];
  onRunStarted: (runId: string) => void;
  onSelectGoal: (goalId: string) => void;
  onCancel: () => Promise<string>;
  onStartSession: () => Promise<string>;
}

/**
 * The chat, which is how the orchestrator is driven.
 *
 * Two things share this box, and the distinction is the whole design: a
 * **command** does something and reports what it did; a **message** is part of
 * the design conversation and goes to the Decision Ledger. Anything the parser
 * does not recognise as a command is a message, so nothing is ever done by
 * accident.
 */
export const ChatStage: FC<ChatStageProps> = ({
  sessionId,
  goalIds,
  onRunStarted,
  onSelectGoal,
  onCancel,
  onStartSession,
}) => {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const feed = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Assigning scrollTop rather than calling scrollTo: the method is
    // absent in some environments, and a chat that throws while trying to
    // scroll is worse than one that does not scroll.
    if (feed.current) feed.current.scrollTop = feed.current.scrollHeight;
  }, [turns]);

  const say = useCallback((turn: Omit<Turn, "id">) => {
    setTurns((current) => [...current, { ...turn, id: nextId() }]);
  }, []);

  const submit = useCallback(async () => {
    const raw = input.trim();
    if (raw === "" || busy) return;
    setInput("");
    say({ author: "you", text: raw });
    setBusy(true);

    const command = parseCommand(raw);
    try {
      switch (command.kind) {
        case "help":
          say({ author: "atlas", text: helpText() });
          break;

        case "run": {
          if (!goalIds.includes(command.goalId)) {
            say({
              author: "atlas",
              text: `This project has no Goal ${command.goalId}.`,
              failed: true,
            });
            break;
          }
          const run = await api.startRun(command.goalId, "dummy");
          onRunStarted(run.id);
          say({
            author: "atlas",
            text: `Started ${run.id} for ${command.goalId}.`,
            action: { label: "Watch it", runId: run.id },
          });
          break;
        }

        case "cancel": {
          const message = await onCancel();
          say({ author: "atlas", text: message });
          break;
        }

        case "show": {
          onSelectGoal(command.goalId);
          say({
            author: "atlas",
            text: `${command.goalId} selected; its gates are in the inspector.`,
            action: { label: "Open the plan", goalId: command.goalId },
          });
          break;
        }

        case "evidence": {
          const goalId = command.goalId;
          if (goalId === null) {
            say({
              author: "atlas",
              text: "Which Goal? Try: evidence P08-G01",
              failed: true,
            });
            break;
          }
          const verification = await api.verification(goalId);
          const lines = verification.gates
            .map((gate) => `${gate.gate}: ${gate.verdict}`)
            .join("\n");
          say({
            author: "atlas",
            text: verification.completable
              ? `${goalId} — every required gate has passing evidence.\n${lines}`
              : `${goalId} — ${verification.blocking}\n${lines}`,
          });
          break;
        }

        case "message": {
          if (command.content === "") break;
          const session = sessionId ?? (await onStartSession());
          await api.sendMessage(session, command.content);
          say({
            author: "atlas",
            text: "Kept in the discussion. Say `help` for what I can do.",
          });
          break;
        }
      }
    } catch (cause: unknown) {
      say({
        author: "atlas",
        text: cause instanceof Error ? cause.message : String(cause),
        failed: true,
      });
    } finally {
      setBusy(false);
    }
  }, [busy, goalIds, input, onCancel, onRunStarted, onSelectGoal, onStartSession, say, sessionId]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div
        ref={feed}
        role="log"
        aria-live="polite"
        aria-label="Conversation"
        style={{
          flex: 1,
          overflowY: "auto",
          padding: space.loose,
          display: "flex",
          flexDirection: "column",
          gap: space.base,
        }}
      >
        {turns.length === 0 && (
          <div style={{ color: text.muted, fontSize: type.ui, maxWidth: 560 }}>
            <p style={{ margin: `0 0 ${space.snug}px` }}>
              Type to talk, or give a command. Commands act; anything else is kept
              as part of the discussion.
            </p>
            <pre
              style={{
                margin: 0,
                padding: space.base,
                background: surface.chrome,
                borderRadius: 6,
                fontSize: type.small,
                whiteSpace: "pre-wrap",
              }}
            >
              {helpText()}
            </pre>
          </div>
        )}

        {turns.map((turn) => (
          <div
            key={turn.id}
            style={{
              alignSelf: turn.author === "you" ? "flex-end" : "flex-start",
              maxWidth: "min(72ch, 88%)",
            }}
          >
            <p
              style={{
                margin: `0 0 ${space.hair}px`,
                color: text.faint,
                fontSize: type.tiny,
                textAlign: turn.author === "you" ? "right" : "left",
              }}
            >
              {turn.author === "you" ? "You" : "Atlas Flow"}
            </p>
            <div
              style={{
                padding: `${space.snug}px ${space.base}px`,
                borderRadius: 10,
                border: `1px solid ${
                  turn.failed ? tone.negative.border : surface.border
                }`,
                background:
                  turn.failed
                    ? tone.negative.bg
                    : turn.author === "you"
                      ? accent.soft
                      : surface.card,
                color: turn.failed ? text.danger : text.primary,
                fontSize: type.ui,
                whiteSpace: "pre-wrap",
              }}
            >
              {turn.text}
              {turn.action && (
                <div style={{ marginTop: space.snug }}>
                  <button
                    type="button"
                    onClick={() => {
                      if (turn.action?.goalId) onSelectGoal(turn.action.goalId);
                      if (turn.action?.runId) onRunStarted(turn.action.runId);
                    }}
                    style={{
                      padding: `${space.hair}px ${space.snug}px`,
                      border: `1px solid ${accent.base}`,
                      borderRadius: 5,
                      background: surface.card,
                      color: accent.base,
                      font: "inherit",
                      fontSize: type.small,
                      cursor: "pointer",
                    }}
                  >
                    {turn.action.label}
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          flex: "0 0 auto",
          display: "flex",
          gap: space.snug,
          padding: space.base,
          borderTop: `1px solid ${surface.border}`,
          background: surface.chrome,
        }}
      >
        <input
          aria-label="Message or command"
          value={input}
          disabled={busy}
          placeholder="Say something, or try: run P08-G01"
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submit();
            }
          }}
          style={{
            flex: 1,
            padding: `${space.snug}px ${space.base}px`,
            border: `1px solid ${surface.border}`,
            borderRadius: 8,
            background: surface.card,
            color: text.primary,
            font: "inherit",
            fontSize: type.ui,
          }}
        />
        <button
          type="button"
          disabled={busy}
          onClick={() => void submit()}
          style={{
            padding: `${space.snug}px ${space.loose}px`,
            border: "none",
            borderRadius: 8,
            background: accent.base,
            color: accent.on,
            font: "inherit",
            fontSize: type.ui,
            fontWeight: 600,
            cursor: busy ? "wait" : "pointer",
          }}
        >
          {busy ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
};

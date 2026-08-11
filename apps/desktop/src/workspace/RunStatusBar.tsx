import type { FC } from "react";
import type { RunDetail } from "../api";
import { EngineStatus } from "./EngineStatus";
import { cancelState } from "../screens/BuildScreen";
import { size, space, surface, text, tone, toneFor, type } from "../theme";

export interface RunSummary {
  runId: string;
  goalId: string;
  state: string;
  done: number;
  total: number;
  model: string | null;
}

/** What the status bar knows about the run, from the run's own detail. */
export function summarise(detail: RunDetail | null): RunSummary | null {
  if (detail === null) return null;
  const terminal = new Set(["SUCCEEDED", "FAILED", "CANCELLED", "SUPERSEDED"]);
  const attempts = detail.attempts;
  return {
    runId: detail.run.id,
    goalId: detail.run.goalId,
    state: detail.run.state,
    done: detail.tasks.filter((task) => terminal.has(task.state)).length,
    total: detail.tasks.length,
    model: attempts.length > 0 ? (attempts[attempts.length - 1].modelId ?? null) : null,
  };
}

/** One line saying what is happening, or that nothing is. */
export function describeRun(summary: RunSummary | null): string {
  if (summary === null) return "Nothing running";
  const progress = summary.total > 0 ? `${summary.done}/${summary.total} tasks` : "no tasks";
  return `${summary.goalId} · ${progress}`;
}

/**
 * Work in flight, never hidden.
 *
 * The previous shell could be executing a run and show no sign of it anywhere
 * in the window: you had to remember you had started one and navigate to find
 * it. For a tool whose entire job is holding work in flight, that was the
 * worst thing about it.
 */
export const RunStatusBar: FC<{
  detail: RunDetail | null;
  epoch: number;
  onCancel: () => void;
  onReveal: () => void;
  onEngineChanged: () => void;
}> = ({ detail, epoch, onCancel, onReveal, onEngineChanged }) => {
  const summary = summarise(detail);
  const cancel = cancelState(summary?.state);
  const colours = summary ? tone[toneFor(summary.state)] : tone.neutral;

  return (
    <footer
      role="status"
      aria-live="polite"
      style={{
        height: size.status,
        flex: "0 0 auto",
        display: "flex",
        alignItems: "center",
        gap: space.base,
        padding: `0 ${space.base}px`,
        borderTop: `1px solid ${surface.border}`,
        background: surface.chrome,
        fontSize: type.small,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: summary ? colours.fg : text.faint,
          flex: "0 0 auto",
        }}
      />

      {summary === null ? (
        <span style={{ color: text.muted }}>Nothing running</span>
      ) : (
        <>
          <button
            type="button"
            onClick={onReveal}
            style={{
              border: "none",
              background: "none",
              padding: 0,
              font: "inherit",
              fontSize: type.small,
              color: text.primary,
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            {describeRun(summary)}
          </button>
          <span style={{ color: colours.fg, fontWeight: 600 }}>{summary.state}</span>
          {summary.model && <span style={{ color: text.faint }}>{summary.model}</span>}
        </>
      )}

      <span
        style={{
          marginLeft: "auto",
          display: "flex",
          alignItems: "center",
          gap: space.base,
        }}
      >
        <EngineStatus epoch={epoch} onChanged={onEngineChanged} />
      </span>

      <button
        type="button"
        disabled={!cancel.enabled}
        onClick={onCancel}
        style={{
          padding: `${space.hair}px ${space.snug}px`,
          border: `1px solid ${cancel.enabled ? tone.negative.border : surface.border}`,
          borderRadius: 5,
          background: cancel.enabled ? tone.negative.bg : "transparent",
          color: cancel.enabled ? text.danger : text.faint,
          font: "inherit",
          fontSize: type.small,
          cursor: cancel.enabled ? "pointer" : "default",
        }}
      >
        {cancel.label}
      </button>
    </footer>
  );
};

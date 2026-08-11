import type { FC } from "react";
import { useCallback, useState } from "react";
import { api, type RunDetail } from "../api";
import { useAsync, usePolling } from "../hooks/useAsync";
import { useAgentStream } from "../hooks/useAgentStream";
import {
  AsyncPanel,
  buttonStyle,
  card,
  muted,
  screen,
  SectionHeading,
  StatusBadge,
} from "../components/Primitives";
import { accent, surface, text } from "../theme";
import { TaskDrawer, taskAttemptSummary } from "../workspace/TaskDrawer";

const ACTIVE_RUN_STATES = new Set(["CREATED", "PLANNING", "READY", "RUNNING"]);

/** What the Cancel button says about a run it cannot stop. */
export function cancelState(runState: string | undefined): {
  enabled: boolean;
  label: string;
} {
  if (runState === undefined) return { enabled: false, label: "Cancel" };
  if (runState === "CANCELLED") return { enabled: false, label: "Cancelled" };
  if (!ACTIVE_RUN_STATES.has(runState)) {
    return { enabled: false, label: "Cancel" };
  }
  return { enabled: true, label: "Cancel" };
}

export const BuildScreen: FC<{ runId: string | null }> = ({ runId }) => {
  const detail = useAsync(
    async () => (runId ? await api.run(runId) : null),
    [runId],
  );
  const [cancelError, setCancelError] = useState<string | null>(null);

  // A run in flight is followed by polling; once it reaches a terminal state
  // there is nothing left to refresh, so the timer stops.
  const isActive = detail.data ? ACTIVE_RUN_STATES.has(detail.data.run.state) : false;
  const cancel = cancelState(detail.data?.run.state);
  usePolling(detail.reload, Boolean(runId) && isActive, 800);

  if (!runId) {
    return (
      <div style={screen}>
        <SectionHeading>Build</SectionHeading>
        <p style={muted}>Start a goal from the Plan tab to watch it execute here.</p>
      </div>
    );
  }

  return (
    <div style={screen}>
      <SectionHeading
        actions={
          <div style={{ display: "flex", gap: "0.4rem" }}>
            <button
              type="button"
              style={buttonStyle}
              disabled={!cancel.enabled}
              onClick={() => {
                setCancelError(null);
                api
                  .cancelRun(runId)
                  .then(() => detail.reload())
                  .catch((cause: unknown) =>
                    setCancelError(
                      cause instanceof Error ? cause.message : String(cause),
                    ),
                  );
              }}
            >
              {cancel.label}
            </button>
            <button type="button" style={buttonStyle} onClick={detail.reload}>
              Refresh
            </button>
          </div>
        }
      >
        Build
      </SectionHeading>

      {cancelError && (
        <p style={{ ...muted, color: text.danger }} role="alert">
          {cancelError}
        </p>
      )}

      <AsyncPanel loading={detail.loading && !detail.data} error={detail.error} onRetry={detail.reload}>
        {detail.data && <RunBody detail={detail.data} live={isActive} />}
      </AsyncPanel>

      <AgentActivityPanel runId={runId} live={isActive} />
    </div>
  );
};

const ACTIVITY_LABELS: Record<string, string> = {
  "atlas.agent.message": "says",
  "atlas.agent.thought": "thinks",
  "atlas.terminal.output": "ran",
  "atlas.file.changed": "changed",
  "atlas.tool.call": "tool",
  "atlas.plan.updated": "plan",
};

const AgentActivityPanel: FC<{ runId: string; live: boolean }> = ({ runId, live }) => {
  const { activity, connected } = useAgentStream(runId, live);

  return (
    <section>
      <SectionHeading>Agent activity</SectionHeading>
      <p style={muted}>
        {live
          ? connected
            ? "Streaming live. Narration is not stored — the event log above is the durable record."
            : "Connecting to the event stream…"
          : "The run is not active."}
      </p>
      {activity.length > 0 && (
        <ol
          style={{
            listStyle: "none",
            padding: "0.5rem",
            margin: 0,
            maxHeight: 220,
            overflowY: "auto",
            border: `1px solid ${surface.border}`,
            borderRadius: 8,
            fontFamily: "ui-monospace, monospace",
            fontSize: "0.75rem",
          }}
          aria-live="polite"
        >
          {activity.map((entry) => (
            <li key={entry.key} style={{ padding: "0.15rem 0", color: text.muted }}>
              <span style={{ color: text.faint }}>
                {ACTIVITY_LABELS[entry.type] ?? entry.type}
              </span>{" "}
              {entry.tool && <strong>{entry.tool} </strong>}
              {entry.paths.length > 0 ? entry.paths.join(", ") : entry.text}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
};

const EVENT_LABELS: Record<string, string> = {
  "atlas.run.started": "Run started",
  "atlas.run.completed": "Run completed",
  "atlas.run.failed": "Run failed",
  "atlas.task.ready": "Task ready",
  "atlas.task.succeeded": "Task succeeded",
  "atlas.task.failed": "Task failed",
  "atlas.attempt.started": "Agent attempt started",
  "atlas.attempt.completed": "Agent attempt completed",
  "atlas.attempt.failed": "Agent attempt failed",
  "atlas.gate.passed": "Verification gate passed",
  "atlas.gate.failed": "Verification gate failed",
  "atlas.state.change": "State changed",
};

const RunBody: FC<{ detail: RunDetail; live: boolean }> = ({ detail, live }) => {
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const attemptsByTask = useCallback(
    (taskId: string) => detail.attempts.filter((attempt) => attempt.taskId === taskId),
    [detail.attempts],
  );
  const selectedTask = detail.tasks.find((task) => task.id === selectedTaskId) ?? null;

  return (
    <>
      <div style={card}>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <strong>{detail.run.goalId}</strong>
          <StatusBadge value={detail.run.state} />
          {live && <span style={muted}>live</span>}
        </div>
        <p style={{ ...muted, margin: "0.25rem 0 0" }}>
          {detail.tasks.length} tasks · {detail.attempts.length} attempts · autonomy {detail.run.autonomy}
        </p>
      </div>

      <section>
        <SectionHeading>What happened</SectionHeading>
        <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.4rem" }} aria-live={live ? "polite" : "off"}>
          {detail.events.map((event) => (
            <li key={event.id} style={{ ...card, padding: "0.65rem 0.8rem", display: "flex", gap: "0.6rem", alignItems: "center" }}>
              <span style={{ color: text.faint, fontFamily: "ui-monospace, monospace", fontSize: "0.72rem" }}>{event.timestamp.slice(11, 19)}</span>
              <strong>{EVENT_LABELS[event.type] ?? event.type}</strong>
              <span style={muted}>{String(event.payload.task_id ?? event.payload.gate ?? "")}</span>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <SectionHeading>Tasks</SectionHeading>
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.5rem" }}>
          {detail.tasks.map((task) => {
            const attempts = attemptsByTask(task.id);
            return (
              <li key={task.id}>
                <button type="button" aria-pressed={selectedTaskId === task.id} onClick={() => setSelectedTaskId(task.id)} style={{ ...card, ...buttonStyle, width: "100%", textAlign: "left", borderColor: selectedTaskId === task.id ? accent.base : surface.border }}>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <StatusBadge value={task.state} />
                    <strong>{task.objective}</strong>
                  </div>
                  <p style={{ ...muted, margin: "0.25rem 0 0" }}>
                    {taskAttemptSummary(attempts)}{task.scope.length > 0 && ` · scope ${task.scope.join(", ")}`}
                  </p>
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      {selectedTask && <TaskDrawer task={selectedTask} attempts={attemptsByTask(selectedTask.id)} onClose={() => setSelectedTaskId(null)} />}

      <details>
        <summary style={{ cursor: "pointer", color: text.muted }}>Technical event log</summary>
        <ol style={{ listStyle: "none", padding: "0.5rem", margin: "0.5rem 0 0", maxHeight: 260, overflowY: "auto", border: `1px solid ${surface.border}`, borderRadius: 8, fontFamily: "ui-monospace, monospace", fontSize: "0.75rem" }}>
          {detail.events.map((event) => <li key={event.id} style={{ padding: "0.15rem 0", color: text.muted }}>{event.timestamp.slice(11, 19)} {event.type}</li>)}
        </ol>
      </details>
    </>
  );
};

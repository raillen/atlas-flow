import type { FC } from "react";
import { useCallback } from "react";
import { api, type RunDetail } from "../api";
import { useAsync, usePolling } from "../hooks/useAsync";
import {
  AsyncPanel,
  buttonStyle,
  card,
  muted,
  screen,
  SectionHeading,
  StatusBadge,
} from "../components/Primitives";

const ACTIVE_RUN_STATES = new Set(["CREATED", "PLANNING", "READY", "RUNNING"]);

export const BuildScreen: FC<{ runId: string | null }> = ({ runId }) => {
  const detail = useAsync(
    async () => (runId ? await api.run(runId) : null),
    [runId],
  );

  // A run in flight is followed by polling; once it reaches a terminal state
  // there is nothing left to refresh, so the timer stops.
  const isActive = detail.data ? ACTIVE_RUN_STATES.has(detail.data.run.state) : false;
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
          <button type="button" style={buttonStyle} onClick={detail.reload}>
            Refresh
          </button>
        }
      >
        Build
      </SectionHeading>

      <AsyncPanel loading={detail.loading && !detail.data} error={detail.error} onRetry={detail.reload}>
        {detail.data && <RunBody detail={detail.data} live={isActive} />}
      </AsyncPanel>
    </div>
  );
};

const RunBody: FC<{ detail: RunDetail; live: boolean }> = ({ detail, live }) => {
  const attemptsByTask = useCallback(
    (taskId: string) => detail.attempts.filter((attempt) => attempt.taskId === taskId),
    [detail.attempts],
  );

  return (
    <>
      <div style={card}>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <strong>{detail.run.goalId}</strong>
          <StatusBadge value={detail.run.state} />
          {live && <span style={muted}>live</span>}
        </div>
        <p style={{ ...muted, margin: "0.25rem 0 0" }}>
          {detail.tasks.length} tasks · {detail.attempts.length} attempts ·{" "}
          autonomy {detail.run.autonomy}
        </p>
      </div>

      <section>
        <SectionHeading>Tasks</SectionHeading>
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.5rem" }}>
          {detail.tasks.map((task) => {
            const attempts = attemptsByTask(task.id);
            const latest = attempts[attempts.length - 1];
            return (
              <li key={task.id} style={card}>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <StatusBadge value={task.state} />
                  <strong>{task.objective}</strong>
                </div>
                <p style={{ ...muted, margin: "0.25rem 0 0" }}>
                  {latest
                    ? `${latest.runner ?? "?"} · ${latest.modelId ?? "default"} · ${latest.state}`
                    : "no attempt yet"}
                  {task.scope.length > 0 && ` · scope ${task.scope.join(", ")}`}
                </p>
                {latest?.errorMsg && (
                  <p style={{ ...muted, color: "#b91c1c", margin: "0.25rem 0 0" }}>
                    {latest.errorMsg}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section>
        <SectionHeading>Event log</SectionHeading>
        <ol
          style={{
            listStyle: "none",
            padding: "0.5rem",
            margin: 0,
            maxHeight: 260,
            overflowY: "auto",
            border: "1px solid #e2e8f0",
            borderRadius: 8,
            fontFamily: "ui-monospace, monospace",
            fontSize: "0.75rem",
          }}
          aria-live={live ? "polite" : "off"}
        >
          {detail.events.map((event) => (
            <li key={event.id} style={{ padding: "0.15rem 0", color: "#475569" }}>
              <span style={{ color: "#94a3b8" }}>
                {event.timestamp.slice(11, 19)}
              </span>{" "}
              {event.type}
            </li>
          ))}
        </ol>
      </section>
    </>
  );
};

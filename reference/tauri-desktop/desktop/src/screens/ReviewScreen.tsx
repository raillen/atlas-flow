import type { FC } from "react";
import { useEffect, useState } from "react";
import type { GoalView, RoutingView, RunDetail } from "../api";
import { api } from "../api";
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

export function describeRegistry(routing: RoutingView): string {
  if (routing.state === "pending") return "Asking the live model registry…";
  if (routing.state === "degraded") {
    return `Live registry unreachable — routing on the policy roster. ${routing.reason}`;
  }
  return `${routing.available.length} model(s) reachable.`;
}

const RoutingPanel: FC = () => {
  const routing = useAsync(() => api.routing(), []);

  return (
    <section>
      <SectionHeading>Model routing</SectionHeading>
      <p style={muted}>
        Routing is evidence about how work was assigned, not a hidden implementation detail.
      </p>
      <AsyncPanel loading={routing.loading} error={routing.error} onRetry={routing.reload}>
        {routing.data && (
          <>
            <div style={card}>
              <StatusBadge value={routing.data.state.toUpperCase()} />
              <span style={{ ...muted, marginLeft: "0.5rem" }}>
                {describeRegistry(routing.data)}
              </span>
            </div>
            <ul style={{ listStyle: "none", padding: 0, margin: "0.4rem 0 0", display: "grid", gap: "0.4rem" }}>
              {routing.data.roles.map((role) => (
                <li key={role.role} style={card}>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <strong style={{ minWidth: 140 }}>{role.role}</strong>
                    <StatusBadge value={role.selected ?? "UNROUTABLE"} />
                    {role.provider && <span style={muted}>{role.provider}</span>}
                  </div>
                  <p style={{ ...muted, margin: "0.25rem 0 0" }}>{role.explanation}</p>
                </li>
              ))}
            </ul>
          </>
        )}
      </AsyncPanel>
    </section>
  );
};

export const ReviewScreen: FC = () => {
  const goals = useAsync(() => api.goals(), []);
  const runs = useAsync(() => api.runs(), []);
  const [goalId, setGoalId] = useState<string | null>(null);
  const goal = goals.data?.find((item) => item.id === goalId) ?? null;
  const verification = useAsync(
    async () => (goalId ? await api.verification(goalId) : null),
    [goalId],
  );
  const latestRun = runs.data?.find((run) => run.goalId === goalId) ?? null;
  const runDetail = useAsync<RunDetail | null>(
    () => (latestRun ? api.run(latestRun.id) : Promise.resolve(null)),
    [latestRun?.id],
  );

  useEffect(() => {
    if (goalId === null && goals.data?.length) setGoalId(goals.data[0].id);
  }, [goalId, goals.data]);

  return (
    <div style={screen}>
      <SectionHeading>Review</SectionHeading>
      <p style={muted}>
        Trace every acceptance criterion to the task, verification evidence and the latest run result.
      </p>

      <AsyncPanel loading={goals.loading} error={goals.error} onRetry={goals.reload}>
        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
          {goals.data?.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={goalId === item.id}
              onClick={() => setGoalId(item.id)}
              style={{ ...buttonStyle, borderColor: goalId === item.id ? accent.base : tone.neutral.border }}
            >
              {item.id}
            </button>
          ))}
        </div>
      </AsyncPanel>

      {goal && (
        <AsyncPanel loading={verification.loading} error={verification.error} onRetry={verification.reload}>
          {verification.data && (
            <>
              <ReviewSummary goal={goal} completable={verification.data.completable} blocking={verification.data.blocking} />
              <ReviewMatrix goal={goal} verification={verification.data} run={runDetail.data} runLoading={runDetail.loading} />
              <section>
                <SectionHeading>Gates</SectionHeading>
                <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.4rem" }}>
                  {verification.data.gates.map((gate) => (
                    <li key={gate.gate} style={card}>
                      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                        <strong style={{ minWidth: 120 }}>{gate.gate}</strong>
                        <StatusBadge value={gate.verdict} />
                        <span style={muted}>{gate.requirement}</span>
                      </div>
                      {gate.details && <p style={{ ...muted, margin: "0.25rem 0 0" }}>{gate.details}</p>}
                    </li>
                  ))}
                </ul>
              </section>
              <section>
                <SectionHeading>Evidence</SectionHeading>
                {verification.data.evidence.length === 0 ? (
                  <p style={muted}>No evidence recorded for this Goal yet.</p>
                ) : (
                  <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.4rem" }}>
                    {verification.data.evidence.map((item) => (
                      <li key={item.id} style={card}>
                        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                          <StatusBadge value={item.verdict} />
                          <strong>{item.gate}</strong>
                          <span style={muted}>{item.kind}</span>
                        </div>
                        {item.uri && <p style={{ ...muted, margin: "0.25rem 0 0" }}>{item.uri}</p>}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </AsyncPanel>
      )}

      <RoutingPanel />
    </div>
  );
};

const ReviewSummary: FC<{ goal: GoalView; completable: boolean; blocking: string }> = ({ goal, completable, blocking }) => (
  <div style={{ ...card, borderColor: completable ? tone.positive.border : tone.waiting.border, background: completable ? tone.positive.bg : tone.waiting.bg }}>
    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
      <StatusBadge value={goal.state} />
      <strong>{completable ? "Every required gate has passing evidence." : "This Goal is not completable yet."}</strong>
    </div>
    {!completable && <p style={{ ...muted, margin: "0.25rem 0 0" }}>{blocking}</p>}
  </div>
);

export const ReviewMatrix: FC<{
  goal: GoalView;
  verification: Awaited<ReturnType<typeof api.verification>>;
  run: RunDetail | null;
  runLoading: boolean;
}> = ({ goal, verification, run, runLoading }) => (
  <section>
    <SectionHeading>Acceptance traceability</SectionHeading>
    <div style={{ overflowX: "auto", marginTop: "0.4rem" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 680 }}>
        <thead>
          <tr style={{ textAlign: "left", color: text.muted, fontSize: "0.75rem" }}>
            <th style={cell}>Criterion</th>
            <th style={cell}>Task</th>
            <th style={cell}>Run</th>
            <th style={cell}>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {goal.acceptance.map((criterion) => {
            const task = run?.tasks.find((item) => item.objective === criterion) ?? null;
            const evidence = verification.evidence.filter((item) => task ? item.taskId === task.id : false);
            const verdict = evidence.find((item) => item.verdict === "PASSED")?.verdict ?? task?.state ?? "PENDING";
            return (
              <tr key={criterion}>
                <td style={cell}>{criterion}</td>
                <td style={cell}>{task?.id ?? (runLoading ? "Loading…" : "Not assigned")}</td>
                <td style={cell}>{run?.run.state ?? "No run"}</td>
                <td style={cell}><StatusBadge value={verdict} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  </section>
);

const cell: React.CSSProperties = {
  padding: "0.6rem 0.5rem",
  borderBottom: `1px solid ${surface.border}`,
  verticalAlign: "top",
};

export const reviewVerdict = (passed: boolean): string => passed ? "PASSED" : "PENDING";

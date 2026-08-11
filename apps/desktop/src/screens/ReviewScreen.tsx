import type { FC } from "react";
import { useState } from "react";
import type { RoutingView } from "../api";
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

/** Human-readable summary of the live model registry's three states. */
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
        Which model each role is routed to, and why. High-risk work is reviewed by
        a model from a different provider whenever one is reachable.
      </p>
      <AsyncPanel
        loading={routing.loading}
        error={routing.error}
        onRetry={routing.reload}
      >
        {routing.data && (
          <>
            <div style={card}>
              <StatusBadge value={routing.data.state.toUpperCase()} />
              <span style={{ ...muted, marginLeft: "0.5rem" }}>
                {describeRegistry(routing.data)}
              </span>
            </div>

            <ul
              style={{
                listStyle: "none",
                padding: 0,
                margin: "0.4rem 0 0",
                display: "grid",
                gap: "0.4rem",
              }}
            >
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

            {routing.data.stats.length > 0 && (
              <ul
                style={{
                  listStyle: "none",
                  padding: 0,
                  margin: "0.4rem 0 0",
                  display: "grid",
                  gap: "0.4rem",
                }}
              >
                {routing.data.stats.map((stat) => (
                  <li key={stat.modelKey} style={card}>
                    <strong>{stat.modelKey}</strong>
                    <span style={{ ...muted, marginLeft: "0.5rem" }}>
                      {stat.successes}/{stat.uses} succeeded ·{" "}
                      {Math.round(stat.averageLatencyMs)} ms average
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </AsyncPanel>
    </section>
  );
};

export const ReviewScreen: FC = () => {
  const goals = useAsync(() => api.goals(), []);
  const [goalId, setGoalId] = useState<string | null>(null);
  const verification = useAsync(
    async () => (goalId ? await api.verification(goalId) : null),
    [goalId],
  );

  return (
    <div style={screen}>
      <SectionHeading>Review</SectionHeading>
      <p style={muted}>
        A Goal reaches DONE only when every gate it declares required has passing
        evidence.
      </p>

      <AsyncPanel loading={goals.loading} error={goals.error} onRetry={goals.reload}>
        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
          {goals.data?.map((goal) => (
            <button
              key={goal.id}
              type="button"
              aria-pressed={goalId === goal.id}
              onClick={() => setGoalId(goal.id)}
              style={{
                ...buttonStyle,
                borderColor: goalId === goal.id ? "#6366f1" : "#cbd5e1",
              }}
            >
              {goal.id}
            </button>
          ))}
        </div>
      </AsyncPanel>

      {goalId && (
        <AsyncPanel
          loading={verification.loading}
          error={verification.error}
          onRetry={verification.reload}
        >
          {verification.data && (
            <>
              <div
                style={{
                  ...card,
                  borderColor: verification.data.completable ? "#bbf7d0" : "#fde68a",
                  background: verification.data.completable ? "#f0fdf4" : "#fffbeb",
                }}
              >
                <strong>
                  {verification.data.completable
                    ? "All required gates have passing evidence."
                    : "Not completable yet"}
                </strong>
                {!verification.data.completable && (
                  <p style={{ ...muted, margin: "0.25rem 0 0" }}>
                    {verification.data.blocking}
                  </p>
                )}
              </div>

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
                      {gate.details && (
                        <p style={{ ...muted, margin: "0.25rem 0 0" }}>{gate.details}</p>
                      )}
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
                        {item.uri && (
                          <p style={{ ...muted, margin: "0.25rem 0 0" }}>{item.uri}</p>
                        )}
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

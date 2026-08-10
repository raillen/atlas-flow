import type { FC } from "react";
import { useState } from "react";
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
    </div>
  );
};

import type { FC } from "react";
import { api, type GoalView } from "../api";
import { AsyncPanel, StatusBadge } from "../components/Primitives";
import { useAsync } from "../hooks/useAsync";
import { size, space, surface, text, type } from "../theme";

/**
 * Everything known about the selected Goal, in one place.
 *
 * Properties scattered across several screens is the antipattern that makes a
 * dense tool unlearnable: you never know where to look, so you look
 * everywhere. Whatever the sidebar has selected, its detail is here.
 */
export const Inspector: FC<{ goal: GoalView | null }> = ({ goal }) => {
  const verification = useAsync(
    async () => (goal ? await api.verification(goal.id) : null),
    [goal?.id],
  );

  return (
    <aside
      aria-label="Inspector"
      style={{
        width: size.inspector,
        flex: "0 0 auto",
        borderLeft: `1px solid ${surface.border}`,
        background: surface.chrome,
        overflowY: "auto",
        padding: space.base,
        fontSize: type.ui,
      }}
    >
      {goal === null ? (
        <p style={{ color: text.muted, margin: 0 }}>
          Select a Goal to see its gates and evidence.
        </p>
      ) : (
        <>
          <h2 style={{ fontSize: type.heading, margin: `0 0 ${space.tight}px` }}>
            {goal.id}
          </h2>
          <p style={{ margin: `0 0 ${space.base}px`, color: text.muted }}>
            {goal.objective}
          </p>

          <Field label="State">
            <StatusBadge value={goal.state} />
          </Field>
          <Field label="Acceptance">
            {goal.acceptance.length} criteri{goal.acceptance.length === 1 ? "on" : "a"}
          </Field>
          {goal.dependencies.length > 0 && (
            <Field label="Depends on">{goal.dependencies.join(", ")}</Field>
          )}

          <h3 style={heading}>Gates</h3>
          <AsyncPanel
            loading={verification.loading && !verification.data}
            error={verification.error}
            onRetry={verification.reload}
          >
            {verification.data && (
              <>
                <ul style={list}>
                  {verification.data.gates.map((gate) => (
                    <li key={gate.gate} style={row}>
                      <span style={{ minWidth: 96 }}>{gate.gate}</span>
                      <StatusBadge value={gate.verdict} />
                    </li>
                  ))}
                </ul>

                <p
                  style={{
                    margin: `${space.snug}px 0 0`,
                    color: verification.data.completable ? text.muted : text.danger,
                    fontSize: type.small,
                  }}
                >
                  {verification.data.completable
                    ? "Every required gate has passing evidence."
                    : verification.data.blocking}
                </p>

                <h3 style={heading}>Evidence</h3>
                {verification.data.evidence.length === 0 ? (
                  <p style={{ margin: 0, color: text.muted, fontSize: type.small }}>
                    Nothing attached yet.
                  </p>
                ) : (
                  <ul style={list}>
                    {verification.data.evidence.map((item) => (
                      <li
                        key={item.id}
                        style={{ ...row, alignItems: "flex-start", flexWrap: "wrap" }}
                      >
                        <StatusBadge value={item.verdict} />
                        <span style={{ fontWeight: 600 }}>{item.gate}</span>
                        <span
                          style={{
                            flexBasis: "100%",
                            color: text.faint,
                            fontSize: type.small,
                            wordBreak: "break-word",
                          }}
                        >
                          {item.uri || item.kind}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </AsyncPanel>
        </>
      )}
    </aside>
  );
};

const Field: FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div style={{ ...row, marginBottom: space.tight }}>
    <span style={{ minWidth: 96, color: text.faint, fontSize: type.small }}>{label}</span>
    <span>{children}</span>
  </div>
);

const heading: React.CSSProperties = {
  fontSize: type.tiny,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  color: text.faint,
  margin: `${space.loose}px 0 ${space.snug}px`,
};

const list: React.CSSProperties = {
  listStyle: "none",
  padding: 0,
  margin: 0,
  display: "grid",
  gap: space.tight,
};

const row: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: space.snug,
};

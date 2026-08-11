import type { FC } from "react";
import { PanelRightClose } from "lucide-react";
import { api, type GoalView } from "../api";
import { AsyncPanel, StatusBadge } from "../components/Primitives";
import { useAsync } from "../hooks/useAsync";
import { size, space, surface, text, type } from "../theme";

/** Details are available on demand, so the workspace can stay focused. */
export const Inspector: FC<{ goal: GoalView | null; onClose: () => void }> = ({ goal, onClose }) => {
  const verification = useAsync(
    async () => (goal ? await api.verification(goal.id) : null),
    [goal?.id],
  );

  return (
    <aside
      className="inspector-panel"
      aria-label="Goal details"
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
      <header className="inspector-header">
        <h2>Details</h2>
        <button
          type="button"
          className="icon-button"
          aria-label="Recolher painel de detalhes"
          title="Recolher painel de detalhes"
          onClick={onClose}
        >
          <PanelRightClose size={15} strokeWidth={1.7} aria-hidden="true" />
        </button>
      </header>

      {goal === null ? (
        <p className="text-muted" style={{ color: text.muted }}>No Goal selected.</p>
      ) : (
        <>
          <section className="inspector-summary" aria-labelledby="selected-goal-title">
            <div className="inspector-summary__title">
              <strong id="selected-goal-title">{goal.id}</strong>
              <StatusBadge value={goal.state} />
            </div>
            <p title={goal.objective}>{goal.objective}</p>
          </section>

          <div className="inspector-meta">
            <span>{goal.acceptance.length} criteria</span>
            {goal.dependencies.length > 0 && <span>{goal.dependencies.length} dependencies</span>}
          </div>

          <AsyncPanel
            loading={verification.loading && !verification.data}
            error={verification.error}
            onRetry={verification.reload}
          >
            {verification.data && (
              <>
                <details className="inspector-details">
                  <summary>
                    <span>Gates</span>
                    <span className="inspector-summary__count">{verification.data.gates.length}</span>
                  </summary>
                  <ul className="inspector-list">
                    {verification.data.gates.map((gate) => (
                      <li key={gate.gate}>
                        <span>{gate.gate}</span>
                        <StatusBadge value={gate.verdict} />
                      </li>
                    ))}
                  </ul>
                  <p className={verification.data.completable ? "text-muted" : "inspector-warning"}>
                    {verification.data.completable
                      ? "All required gates pass."
                      : verification.data.blocking}
                  </p>
                </details>

                <details className="inspector-details">
                  <summary>
                    <span>Evidence</span>
                    <span className="inspector-summary__count">{verification.data.evidence.length}</span>
                  </summary>
                  {verification.data.evidence.length === 0 ? (
                    <p className="text-muted">Nothing attached.</p>
                  ) : (
                    <ul className="inspector-list">
                      {verification.data.evidence.map((item) => (
                        <li key={item.id}>
                          <StatusBadge value={item.verdict} />
                          <span title={item.uri || item.kind}>{item.gate}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </details>
              </>
            )}
          </AsyncPanel>
        </>
      )}
    </aside>
  );
};

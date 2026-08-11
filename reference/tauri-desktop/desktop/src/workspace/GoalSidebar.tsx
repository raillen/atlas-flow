import type { FC } from "react";
import type { GoalView } from "../api";
import { StatusBadge } from "../components/Primitives";
import { accent, size, space, surface, text, type } from "../theme";

/** Goals grouped by the phase they belong to, in phase order. */
export function groupByPhase(goals: GoalView[]): [string, GoalView[]][] {
  const phases = new Map<string, GoalView[]>();
  goals.forEach((goal) => {
    const bucket = phases.get(goal.phase) ?? [];
    bucket.push(goal);
    phases.set(goal.phase, bucket);
  });
  return [...phases.entries()].sort(([a], [b]) => a.localeCompare(b));
}

/** How far through its Goals a project is, as a sentence and a fraction. */
export function progressOf(goals: GoalView[]): { done: number; total: number; label: string } {
  const done = goals.filter((goal) => goal.state === "DONE").length;
  const total = goals.length;
  if (total === 0) return { done: 0, total: 0, label: "No Goals declared" };
  return { done, total, label: `${done} of ${total} Goals done` };
}

/**
 * The context, always visible.
 *
 * This does not change when the stage changes: what a person is working on
 * outlives which view they are looking at, and rebuilding that context after
 * every navigation is the thing that made the old five-tab shell tiring.
 */
export const GoalSidebar: FC<{
  goals: GoalView[];
  selected: string | null;
  onSelect: (goalId: string) => void;
}> = ({ goals, selected, onSelect }) => {
  const progress = progressOf(goals);

  return (
    <nav
      aria-label="Goals"
      style={{
        width: size.sidebar,
        flex: "0 0 auto",
        borderRight: `1px solid ${surface.border}`,
        background: surface.chrome,
        overflowY: "auto",
        padding: space.snug,
      }}
    >
      <div className="goal-sidebar__header" title={progress.label}>
        <span>Goals</span>
        <span aria-label={progress.label}>{progress.done}/{progress.total}</span>
      </div>

      {groupByPhase(goals).map(([phase, phaseGoals]) => (
        <div key={phase} style={{ marginBottom: space.base }}>
          <p
            style={{
              margin: `0 0 ${space.hair}px`,
              padding: `0 ${space.tight}px`,
              color: text.faint,
              fontSize: type.tiny,
              fontWeight: 500,
            }}
          >
            {phase}
          </p>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {phaseGoals.map((goal) => (
              <li key={goal.id}>
                <button
                  type="button"
                  aria-current={selected === goal.id ? "true" : undefined}
                  onClick={() => onSelect(goal.id)}
                  title={goal.objective}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: space.snug,
                    width: "100%",
                    textAlign: "left",
                    padding: `${space.tight}px ${space.tight}px`,
                    border: "none",
                    borderRadius: 5,
                    borderLeft: `2px solid ${
                      selected === goal.id ? accent.base : "transparent"
                    }`,
                    background:
                      selected === goal.id ? surface.selected : "transparent",
                    color: text.primary,
                    font: "inherit",
                    fontSize: type.ui,
                    cursor: "pointer",
                  }}
                >
                  <StatusBadge value={goal.state} />
                  <span
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {goal.title}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {goals.length === 0 && (
        <p style={{ padding: space.snug, color: text.muted, fontSize: type.small }}>
          This project declares no Goals.
        </p>
      )}
    </nav>
  );
};

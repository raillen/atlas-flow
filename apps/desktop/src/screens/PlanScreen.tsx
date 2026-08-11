import type { FC } from "react";
import { useCallback, useState } from "react";
import { api, type GoalView, type TaskView } from "../api";
import { useAsync } from "../hooks/useAsync";
import { TaskGraph } from "../components/TaskGraph";
import {
  AsyncPanel,
  buttonStyle,
  card,
  muted,
  screen,
  SectionHeading,
  StatusBadge,
} from "../components/Primitives";
import { accent, surface, tone } from "../theme";

/**
 * Lays the plan out in dependency layers.
 *
 * Layer 0 holds tasks with no dependencies; each later layer holds tasks whose
 * dependencies all sit in earlier layers. That is exactly the order the
 * scheduler releases work in, so the picture matches what will actually run.
 */
export function layerTasks(tasks: TaskView[]): TaskView[][] {
  const byId = new Map(tasks.map((task) => [task.id, task]));
  const depth = new Map<string, number>();

  const resolve = (task: TaskView, seen: Set<string>): number => {
    const cached = depth.get(task.id);
    if (cached !== undefined) return cached;
    if (seen.has(task.id)) return 0;
    seen.add(task.id);

    const parents = task.dependencies
      .map((id) => byId.get(id))
      .filter((value): value is TaskView => value !== undefined);
    const value = parents.length
      ? Math.max(...parents.map((parent) => resolve(parent, seen))) + 1
      : 0;

    depth.set(task.id, value);
    return value;
  };

  tasks.forEach((task) => resolve(task, new Set()));

  const layers: TaskView[][] = [];
  tasks.forEach((task) => {
    const level = depth.get(task.id) ?? 0;
    (layers[level] ??= []).push(task);
  });
  return layers.filter(Boolean);
}

const GoalRow: FC<{ goal: GoalView; onRun: (id: string) => void; busy: boolean }> = ({
  goal,
  onRun,
  busy,
}) => (
  <li style={{ ...card, display: "flex", gap: "1rem", alignItems: "flex-start" }}>
    <div style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
        <strong>{goal.id}</strong>
        <span>{goal.title}</span>
        <StatusBadge value={goal.state} />
      </div>
      <p style={{ ...muted, margin: "0.25rem 0 0" }}>{goal.objective}</p>
      <p style={{ ...muted, margin: "0.25rem 0 0" }}>
        {goal.acceptance.length} acceptance criteria
        {goal.dependencies.length > 0 && ` · depends on ${goal.dependencies.join(", ")}`}
      </p>
    </div>
    <button
      type="button"
      style={buttonStyle}
      disabled={busy}
      onClick={() => onRun(goal.id)}
    >
      {busy ? "Starting…" : "Run goal"}
    </button>
  </li>
);

export const PlanScreen: FC<{ onRunStarted: (runId: string) => void }> = ({
  onRunStarted,
}) => {
  const goals = useAsync(() => api.goals(), []);
  const [starting, setStarting] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const runGoal = useCallback(
    async (goalId: string) => {
      setStarting(goalId);
      setFailure(null);
      try {
        const run = await api.startRun(goalId, "dummy");
        onRunStarted(run.id);
      } catch (cause) {
        setFailure(cause instanceof Error ? cause.message : String(cause));
      } finally {
        setStarting(null);
      }
    },
    [onRunStarted],
  );

  const plan = useAsync(
    async () => (selected ? layerTasks((await api.run(selected)).tasks) : []),
    [selected],
  );

  return (
    <div style={screen}>
      <SectionHeading>Plan</SectionHeading>
      <p style={muted}>
        Goals come from Git. Starting one decomposes it into a task per acceptance
        criterion and schedules it.
      </p>

      {failure && (
        <div style={{ ...card, borderColor: tone.negative.border, background: tone.negative.bg }} role="alert">
          {failure}
        </div>
      )}

      <AsyncPanel
        loading={goals.loading}
        error={goals.error}
        onRetry={goals.reload}
        isEmpty={goals.data?.length === 0}
        emptyMessage="This project declares no Goals."
      >
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.5rem" }}>
          {goals.data?.map((goal) => (
            <GoalRow
              key={goal.id}
              goal={goal}
              busy={starting === goal.id}
              onRun={runGoal}
            />
          ))}
        </ul>
      </AsyncPanel>

      {selected && (
        <section>
          <SectionHeading>Task graph</SectionHeading>
          <AsyncPanel loading={plan.loading} error={plan.error} onRetry={plan.reload}>
            <TaskGraph layers={plan.data ?? []} />
          </AsyncPanel>
        </section>
      )}

      <PlanRunPicker onSelect={setSelected} selected={selected} />
    </div>
  );
};

const PlanRunPicker: FC<{ selected: string | null; onSelect: (id: string) => void }> = ({
  selected,
  onSelect,
}) => {
  const runs = useAsync(() => api.runs(), []);

  return (
    <section>
      <SectionHeading actions={<button type="button" style={buttonStyle} onClick={runs.reload}>Refresh</button>}>
        Runs
      </SectionHeading>
      <AsyncPanel
        loading={runs.loading}
        error={runs.error}
        onRetry={runs.reload}
        isEmpty={runs.data?.length === 0}
        emptyMessage="No run has been started yet."
      >
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.4rem" }}>
          {runs.data?.map((run) => (
            <li key={run.id}>
              <button
                type="button"
                aria-pressed={selected === run.id}
                onClick={() => onSelect(run.id)}
                style={{
                  ...card,
                  ...buttonStyle,
                  width: "100%",
                  textAlign: "left",
                  borderColor: selected === run.id ? accent.base : surface.border,
                }}
              >
                <strong>{run.goalId}</strong> <StatusBadge value={run.state} />
                <span style={muted}> · {run.taskCount} tasks</span>
              </button>
            </li>
          ))}
        </ul>
      </AsyncPanel>
    </section>
  );
};

import type { FC } from "react";
import { useCallback, useState } from "react";
import { api, type GoalView, type PlanView, type TaskView } from "../api";
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

function taskViews(plan: PlanView): TaskView[] {
  return plan.tasks.map((task) => ({
    id: task.id,
    objective: task.objective,
    state: plan.state,
    role: task.capabilities[0] ?? null,
    risk: task.risk,
    scope: task.writeScope,
    dependencies: task.dependencies,
  }));
}

const GoalRow: FC<{
  goal: GoalView;
  selected: boolean;
  onSelect: () => void;
}> = ({ goal, selected, onSelect }) => (
  <li>
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      style={{
        ...card,
        ...buttonStyle,
        width: "100%",
        textAlign: "left",
        borderColor: selected ? accent.base : surface.border,
      }}
    >
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
    </button>
  </li>
);

export const PlanScreen: FC<{ onRunStarted: (runId: string) => void }> = ({
  onRunStarted,
}) => {
  const goals = useAsync(() => api.goals(), []);
  const [selected, setSelected] = useState<string | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const selectedGoal = goals.data?.find((goal) => goal.id === selected) ?? null;
  const plan = useAsync(
    () => (planId ? api.plan(planId) : Promise.resolve(null)),
    [planId],
  );
  const historicalPlans = useAsync(
    () => (selected ? api.plans(selected) : Promise.resolve([])),
    [selected],
  );

  const createPlan = useCallback(async () => {
    if (!selected) return;
    setFailure(null);
    try {
      const created = await api.createPlan(selected);
      setPlanId(created.id);
      historicalPlans.reload();
    } catch (cause: unknown) {
      setFailure(cause instanceof Error ? cause.message : String(cause));
    }
  }, [historicalPlans, selected]);

  const lockPlan = useCallback(async () => {
    if (!planId) return;
    setFailure(null);
    try {
      await api.lockPlan(planId);
      plan.reload();
      historicalPlans.reload();
    } catch (cause: unknown) {
      setFailure(cause instanceof Error ? cause.message : String(cause));
    }
  }, [historicalPlans, plan, planId]);

  const runPlan = useCallback(async () => {
    if (!selected || !plan.data || plan.data.state !== "LOCKED") return;
    setFailure(null);
    try {
      const run = await api.startRun(selected, plan.data.runner, plan.data.id);
      onRunStarted(run.id);
    } catch (cause: unknown) {
      setFailure(cause instanceof Error ? cause.message : String(cause));
    }
  }, [onRunStarted, plan.data, selected]);

  return (
    <div style={screen}>
      <SectionHeading>Plan</SectionHeading>
      <p style={muted}>
        Create a reviewable snapshot from the Goal, inspect its DAG and lock it before any agent starts.
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
        emptyMessage="This project declares no executable Goals."
      >
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.5rem" }}>
          {goals.data?.map((goal) => (
            <GoalRow key={goal.id} goal={goal} selected={selected === goal.id} onSelect={() => {
              setSelected(goal.id);
              setPlanId(null);
            }} />
          ))}
        </ul>
      </AsyncPanel>

      {selectedGoal && (
        <section>
          <SectionHeading
            actions={
              <button type="button" style={{ ...buttonStyle, background: accent.base, color: accent.on }} onClick={() => void createPlan()}>
                Create plan
              </button>
            }
          >
            {selectedGoal.id} plan
          </SectionHeading>
          <p style={muted}>{selectedGoal.objective}</p>

          <AsyncPanel loading={historicalPlans.loading} error={historicalPlans.error} onRetry={historicalPlans.reload}>
            {historicalPlans.data && historicalPlans.data.length > 0 && (
              <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
                {historicalPlans.data.map((item) => (
                  <button key={item.id} type="button" style={{ ...buttonStyle, borderColor: item.id === planId ? accent.base : surface.border }} onClick={() => setPlanId(item.id)}>
                    {item.id} · {item.state}
                  </button>
                ))}
              </div>
            )}
          </AsyncPanel>

          {planId && (
            <AsyncPanel loading={plan.loading} error={plan.error} onRetry={plan.reload}>
              {plan.data && <PlanReview plan={plan.data} onLock={() => void lockPlan()} onRun={() => void runPlan()} />}
            </AsyncPanel>
          )}
        </section>
      )}
    </div>
  );
};

const PlanReview: FC<{ plan: PlanView; onLock: () => void; onRun: () => void }> = ({ plan, onLock, onRun }) => {
  const tasks = taskViews(plan);
  return (
    <>
      <div style={{ ...card, display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <StatusBadge value={plan.state} />
        <span style={muted}>{tasks.length} tasks · {plan.autonomy} · runner {plan.runner}</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: "0.4rem" }}>
          {plan.state === "DRAFT" && <button type="button" style={buttonStyle} onClick={onLock}>Lock plan</button>}
          {plan.state === "LOCKED" && <button type="button" style={{ ...buttonStyle, background: accent.base, color: accent.on }} onClick={onRun}>Run locked plan</button>}
        </span>
      </div>
      <SectionHeading>Dependency graph</SectionHeading>
      <TaskGraph layers={layerTasks(tasks)} />
      <SectionHeading>Task contract</SectionHeading>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.4rem" }}>
        {plan.tasks.map((task) => (
          <li key={task.id} style={card}>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <strong>{task.objective}</strong>
              <StatusBadge value={task.risk} />
            </div>
            <p style={{ ...muted, margin: "0.25rem 0 0" }}>
              {task.capabilities.join(", ") || "core implementation"} · {task.writeScope.join(", ") || "scope to be resolved by runner"}
            </p>
          </li>
        ))}
      </ul>
    </>
  );
};

export const planStateTone = (state: string) => tone[state === "LOCKED" ? "active" : "neutral"];

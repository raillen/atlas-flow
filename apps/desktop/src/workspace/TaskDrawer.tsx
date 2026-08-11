import type { FC } from "react";
import type { AttemptView, TaskView } from "../api";
import { buttonStyle, card, muted, SectionHeading, StatusBadge } from "../components/Primitives";
import { space, surface, text, type } from "../theme";

export const TaskDrawer: FC<{
  task: TaskView;
  attempts: AttemptView[];
  onClose: () => void;
}> = ({ task, attempts, onClose }) => {
  const latest = attempts[attempts.length - 1] ?? null;

  return (
    <aside
      aria-label={`Task details: ${task.objective}`}
      style={{
        ...card,
        borderColor: surface.border,
        background: surface.raised,
        display: "grid",
        gap: space.snug,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: space.snug }}>
        <div style={{ flex: 1 }}>
          <p style={{ ...muted, margin: 0, fontSize: type.small }}>Selected task</p>
          <h3 style={{ margin: `${space.tight}px 0 0`, fontSize: type.heading }}>{task.objective}</h3>
        </div>
        <button type="button" style={buttonStyle} onClick={onClose}>Close</button>
      </div>

      <div style={{ display: "flex", gap: space.snug, flexWrap: "wrap" }}>
        <StatusBadge value={task.state} />
        <StatusBadge value={task.risk} />
        {task.role && <span style={muted}>role: {task.role}</span>}
      </div>

      <div>
        <SectionHeading>Execution contract</SectionHeading>
        <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: `${space.tight}px ${space.base}px`, margin: `${space.snug}px 0 0`, fontSize: type.small }}>
          <dt style={{ color: text.faint }}>Dependencies</dt>
          <dd style={{ margin: 0 }}>{task.dependencies.join(", ") || "None"}</dd>
          <dt style={{ color: text.faint }}>Write scope</dt>
          <dd style={{ margin: 0 }}>{task.scope.join(", ") || "Resolved by runner"}</dd>
          <dt style={{ color: text.faint }}>Attempts</dt>
          <dd style={{ margin: 0 }}>{attempts.length}</dd>
        </dl>
      </div>

      {latest && (
        <div style={{ ...card, padding: space.snug }}>
          <div style={{ display: "flex", gap: space.snug, alignItems: "center" }}>
            <strong>Latest attempt</strong>
            <StatusBadge value={latest.state} />
          </div>
          <p style={{ ...muted, margin: `${space.tight}px 0 0` }}>
            {latest.runner ?? "Unknown runner"} · {latest.modelId ?? "Default model"}
          </p>
          {latest.errorMsg && <p style={{ margin: `${space.tight}px 0 0`, color: text.danger }}>{latest.errorMsg}</p>}
        </div>
      )}
    </aside>
  );
};

export const taskAttemptSummary = (attempts: AttemptView[]): string => {
  const latest = attempts[attempts.length - 1];
  if (!latest) return "No attempt yet";
  return `${latest.runner ?? "runner?"} · ${latest.modelId ?? "default"} · ${latest.state}`;
};

import type { FC } from "react";
import { api, type ProjectInspection, type RunView } from "../api";
import { useAsync } from "../hooks/useAsync";
import { AsyncPanel, buttonStyle, card, muted, SectionHeading, StatusBadge, screen } from "../components/Primitives";
import { accent, space, text, tone } from "../theme";

const ACTIVE = new Set(["CREATED", "PLANNING", "READY", "RUNNING", "VERIFYING", "REVIEWING"]);

export const AttentionStage: FC<{
  inspection: ProjectInspection | null;
  goalsCount: number;
  onOpenDefine: () => void;
  onOpenPlan: () => void;
  onOpenRun: (runId: string) => void;
  onAdapt: () => void;
}> = ({ inspection, goalsCount, onOpenDefine, onOpenPlan, onOpenRun, onAdapt }) => {
  const runs = useAsync(
    () => inspection?.capabilities?.canRun ? api.runs() : Promise.resolve([] as RunView[]),
    [inspection?.root, inspection?.mode],
  );
  const activeRuns = (runs.data ?? []).filter((run) => ACTIVE.has(run.state));
  const blocked = (runs.data ?? []).filter((run) => run.state === "BLOCKED" || run.state === "FAILED");

  return (
    <div style={screen}>
      <div>
        <p style={{ ...muted, margin: 0 }}>Command center</p>
        <h1 style={{ margin: `${space.tight}px 0 0`, fontSize: "1.35rem" }}>What needs attention?</h1>
      </div>

      {inspection && inspection.capabilities && !inspection.capabilities.canPlan && (
        <section style={{ ...card, borderColor: tone.waiting.border, background: tone.waiting.bg }}>
          <StatusBadge value={inspection.mode} />
          <h2 style={{ fontSize: "1rem", margin: `${space.snug}px 0 ${space.tight}px` }}>
            This project is explorable, not executable yet.
          </h2>
          <p style={{ ...muted, margin: 0 }}>{inspection.recommendation}</p>
          {inspection.capabilities?.canAdapt && (
            <button type="button" style={{ ...buttonStyle, marginTop: space.base, background: accent.base, color: accent.on, borderColor: accent.base }} onClick={onAdapt}>
              Review Project Atlas adaptation
            </button>
          )}
        </section>
      )}

      <section>
        <SectionHeading>Next actions</SectionHeading>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: space.snug, marginTop: space.snug }}>
          <ActionCard title="Define the work" detail="Discuss intent, decisions and open questions." action="Open Define" onClick={onOpenDefine} />
          <ActionCard title="Review a Goal plan" detail={goalsCount ? `${goalsCount} Goal(s) available from Git.` : "No executable Goals yet."} action="Open Plan" onClick={onOpenPlan} disabled={!inspection?.capabilities?.canPlan} />
          <ActionCard title="Recover context" detail="Return to persisted discussions, runs and evidence." action="Open Knowledge" onClick={onOpenDefine} />
        </div>
      </section>

      <section>
        <SectionHeading>Runs requiring attention</SectionHeading>
        <AsyncPanel loading={runs.loading} error={runs.error} onRetry={runs.reload} isEmpty={!runs.loading && activeRuns.length === 0 && blocked.length === 0} emptyMessage="No active or blocked runs.">
          <div style={{ display: "grid", gap: space.snug, marginTop: space.snug }}>
            {[...activeRuns, ...blocked].map((run) => <RunCard key={run.id} run={run} onOpen={() => onOpenRun(run.id)} />)}
          </div>
        </AsyncPanel>
      </section>

      <section style={{ ...card, background: tone.active.bg, borderColor: tone.active.border }}>
        <strong>Atlas Flow keeps the project truth in Git.</strong>
        <p style={{ ...muted, margin: `${space.tight}px 0 0` }}>
          Operational state, attempts and evidence remain available after a restart; no action here silently changes canonical documentation.
        </p>
      </section>
    </div>
  );
};

const ActionCard: FC<{ title: string; detail: string; action: string; onClick: () => void; disabled?: boolean }> = ({ title, detail, action, onClick, disabled }) => (
  <article style={{ ...card, display: "flex", flexDirection: "column", gap: space.snug }}>
    <strong>{title}</strong>
    <p style={{ ...muted, margin: 0, flex: 1 }}>{detail}</p>
    <button type="button" style={buttonStyle} disabled={disabled} onClick={onClick}>{action}</button>
  </article>
);

const RunCard: FC<{ run: RunView; onOpen: () => void }> = ({ run, onOpen }) => (
  <button type="button" onClick={onOpen} style={{ ...card, ...buttonStyle, textAlign: "left", display: "flex", gap: space.snug, alignItems: "center", borderColor: run.state === "BLOCKED" || run.state === "FAILED" ? tone.negative.border : accent.base }}>
    <StatusBadge value={run.state} />
    <span style={{ flex: 1 }}><strong>{run.goalId}</strong><span style={{ ...muted, marginLeft: space.snug }}>{run.taskCount} tasks</span></span>
    <span style={{ color: text.muted }}>Open run</span>
  </button>
);

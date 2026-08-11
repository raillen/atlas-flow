import type { FC } from "react";
import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ListChecks,
  MessageSquare,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Settings2,
  Sun,
  type LucideIcon,
} from "lucide-react";
import { api, type GoalView, type ProjectInspection } from "../api";
import { AsyncPanel } from "../components/Primitives";
import { desktop } from "../desktop";
import { useAsync, usePolling } from "../hooks/useAsync";
import { BuildScreen } from "../screens/BuildScreen";
import { DiscussScreen } from "../screens/DiscussScreen";
import { PlanScreen } from "../screens/PlanScreen";
import { ProjectScreen } from "../screens/ProjectScreen";
import { ReviewScreen } from "../screens/ReviewScreen";
import { size, space, surface, text, type } from "../theme";
import { AdaptationWizard } from "./AdaptationWizard";
import { AttentionStage } from "./AttentionStage";
import { GoalSidebar } from "./GoalSidebar";
import { Inspector } from "./Inspector";
import { ProjectExplorer } from "./ProjectExplorer";
import { ProjectModeBanner } from "./ProjectModeBanner";
import { ProjectSwitcher } from "./ProjectSwitcher";
import { RunStatusBar } from "./RunStatusBar";
import { SettingsDrawer } from "./SettingsDrawer";
import { ThemeProvider, useTheme } from "../theme-context";

export const STAGES = ["attention", "define", "plan", "run", "review", "knowledge"] as const;
export type Stage = (typeof STAGES)[number];

export const STAGE_LABELS: Record<Stage, string> = {
  attention: "Attention",
  define: "Define",
  plan: "Plan",
  run: "Run",
  review: "Review",
  knowledge: "Knowledge",
};

export const STAGE_PURPOSE: Record<Stage, string> = {
  attention: "See what needs attention",
  define: "Decide what to build",
  plan: "Review what a Goal will take",
  run: "Supervise agent work",
  review: "Verify it can be called done",
  knowledge: "Read project context",
};

const STAGE_ICONS: Record<Stage, LucideIcon> = {
  attention: AlertCircle,
  define: MessageSquare,
  plan: ListChecks,
  run: Activity,
  review: CheckCircle2,
  knowledge: BookOpen,
};

export function nextStageIndex(key: string, current: number, count: number): number | null {
  switch (key) {
    case "ArrowRight":
      return (current + 1) % count;
    case "ArrowLeft":
      return (current - 1 + count) % count;
    case "Home":
      return 0;
    case "End":
      return count - 1;
    default:
      return null;
  }
}

const ACTIVE_RUN_STATES = new Set(["CREATED", "PLANNING", "READY", "RUNNING"]);

function stageEnabled(stage: Stage, inspection: ProjectInspection | null): boolean {
  if (inspection === null || !inspection.capabilities) return stage === "attention" || stage === "define" || stage === "knowledge";
  if (stage === "plan") return inspection.capabilities.canPlan;
  if (stage === "run") return inspection.capabilities.canRun;
  if (stage === "review") return inspection.capabilities.canReview;
  return true;
}

const WorkspaceShell: FC = () => {
  const { mode, toggle } = useTheme();
  const [stage, setStage] = useState<Stage>("attention");
  const [projectEpoch, setProjectEpoch] = useState(0);
  const [selectedGoal, setSelectedGoal] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [root, setRoot] = useState<string | null>(null);
  const [adaptationOpen, setAdaptationOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [goalsOpen, setGoalsOpen] = useState(true);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const inspection = useAsync(() => api.inspection(), [projectEpoch]);
  const goals = useAsync(
    () => inspection.data?.capabilities?.canPlan ? api.goals() : Promise.resolve([] as GoalView[]),
    [projectEpoch, inspection.data?.mode],
  );
  const run = useAsync(
    async () => (runId ? await api.run(runId) : null),
    [runId, projectEpoch],
  );

  const active = run.data ? ACTIVE_RUN_STATES.has(run.data.run.state) : false;
  usePolling(run.reload, Boolean(runId) && active, 900);
  usePolling(inspection.reload, inspection.error !== null, 1500);
  usePolling(goals.reload, goals.error !== null, 1500);

  useEffect(() => {
    void desktop.projectRoot().then((value) => setRoot(value ?? null));
  }, [projectEpoch]);

  useEffect(() => {
    if (selectedGoal === null && goals.data && goals.data.length > 0) {
      setSelectedGoal(goals.data[0].id);
    }
  }, [goals.data, selectedGoal]);

  useEffect(() => {
    if (inspection.data?.mode && inspection.data.mode !== "atlas-ready") {
      setAdaptationOpen(true);
    }
  }, [inspection.data]);

  const goal: GoalView | null =
    goals.data?.find((item) => item.id === selectedGoal) ?? null;

  const onProjectOpened = useCallback(() => {
    setStage("attention");
    setSelectedGoal(null);
    setRunId(null);
    setAdaptationOpen(false);
    setProjectEpoch((value) => value + 1);
  }, []);

  const onAdaptationApplied = useCallback(() => {
    setAdaptationOpen(false);
    setStage("define");
    setProjectEpoch((value) => value + 1);
  }, []);

  const cancelRun = useCallback(async () => {
    if (runId === null) return "Nothing is running.";
    try {
      await api.cancelRun(runId);
      run.reload();
      return `Asked ${runId} to stop.`;
    } catch (cause: unknown) {
      return cause instanceof Error ? cause.message : String(cause);
    }
  }, [runId, run]);

  const showRun = useCallback((id: string) => {
    setRunId(id);
    setStage("run");
  }, []);

  const selectStage = useCallback((next: Stage) => {
    if (stageEnabled(next, inspection.data)) setStage(next);
  }, [inspection.data]);

  const [keyboardMove, setKeyboardMove] = useState(false);
  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const current = STAGES.indexOf(stage);
      let next = nextStageIndex(event.key, current, STAGES.length);
      if (next === null) return;
      for (let attempts = 0; attempts < STAGES.length && !stageEnabled(STAGES[next], inspection.data); attempts += 1) {
        next = event.key === "ArrowLeft" ? (next - 1 + STAGES.length) % STAGES.length : (next + 1) % STAGES.length;
      }
      if (!stageEnabled(STAGES[next], inspection.data)) return;
      event.preventDefault();
      setStage(STAGES[next]);
      setKeyboardMove(true);
    },
    [inspection.data, stage],
  );

  useEffect(() => {
    if (!keyboardMove) return;
    setKeyboardMove(false);
    document.getElementById(`stage-${stage}`)?.focus();
  }, [keyboardMove, stage]);

  return (
    <div
      style={{
        height: "100dvh",
        display: "flex",
        flexDirection: "column",
        background: surface.page,
        color: text.primary,
        fontSize: type.ui,
      }}
    >
      <header
        style={{
          height: size.header,
          flex: "0 0 auto",
          display: "flex",
          alignItems: "center",
          gap: space.snug,
          padding: `0 ${space.base}px`,
          borderBottom: `1px solid ${surface.border}`,
          background: surface.chrome,
        }}
      >
        <ProjectSwitcher root={root} onOpened={onProjectOpened} />
        <div role="tablist" aria-label="Workspace stages" onKeyDown={onKeyDown} style={{ display: "flex", gap: space.hair }}>
          {STAGES.map((key) => {
            const enabled = stageEnabled(key, inspection.data);
            const StageIcon = STAGE_ICONS[key];
            return (
              <button
                key={key}
                className="stage-tab"
                role="tab"
                id={`stage-${key}`}
                aria-label={STAGE_LABELS[key]}
                aria-selected={stage === key}
                aria-controls={`stage-panel-${key}`}
                aria-disabled={!enabled}
                tabIndex={stage === key ? 0 : -1}
                title={enabled ? STAGE_PURPOSE[key] : `${STAGE_PURPOSE[key]}. Available after Project Atlas adaptation.`}
                disabled={!enabled}
                onClick={() => selectStage(key)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: space.tight,
                  padding: `${space.tight}px ${space.snug}px`,
                  border: "none",
                  borderRadius: 6,
                  background: stage === key ? surface.card : "transparent",
                  boxShadow: stage === key ? `inset 0 0 0 1px ${surface.border}` : "none",
                  color: enabled ? (stage === key ? text.primary : text.muted) : text.faint,
                  font: "inherit",
                  fontSize: type.ui,
                  fontWeight: stage === key ? 500 : 400,
                  cursor: enabled ? "pointer" : "not-allowed",
                }}
              >
                <StageIcon size={13} strokeWidth={1.6} aria-hidden="true" />
                {stage === key && <span className="stage-tab__label">{STAGE_LABELS[key]}</span>}
              </button>
            );
          })}
        </div>
        <button
          type="button"
          className="icon-button panel-toggle"
          aria-label={goalsOpen ? "Recolher painel de Goals" : "Expandir painel de Goals"}
          aria-expanded={goalsOpen}
          title={goalsOpen ? "Recolher painel de Goals" : "Expandir painel de Goals"}
          onClick={() => setGoalsOpen((value) => !value)}
          style={{
            border: `1px solid ${surface.border}`,
            background: goalsOpen ? surface.selected : "transparent",
          }}
        >
          {goalsOpen ? <PanelLeftClose size={15} strokeWidth={1.7} aria-hidden="true" /> : <PanelLeftOpen size={15} strokeWidth={1.7} aria-hidden="true" />}
        </button>
        <button
          type="button"
          className="icon-button panel-toggle"
          aria-label={inspectorOpen ? "Recolher painel de detalhes" : "Expandir painel de detalhes"}
          aria-expanded={inspectorOpen}
          title={inspectorOpen ? "Recolher painel de detalhes" : "Expandir painel de detalhes"}
          onClick={() => setInspectorOpen((value) => !value)}
          style={{
            border: `1px solid ${surface.border}`,
            background: inspectorOpen ? surface.selected : "transparent",
          }}
        >
          {inspectorOpen ? <PanelRightClose size={15} strokeWidth={1.7} aria-hidden="true" /> : <PanelRightOpen size={15} strokeWidth={1.7} aria-hidden="true" />}
        </button>
        <button
          type="button"
          className="icon-button theme-toggle"
          aria-label={mode === "dark" ? "Ativar tema claro" : "Ativar tema escuro"}
          title={mode === "dark" ? "Ativar tema claro" : "Ativar tema escuro"}
          onClick={toggle}
          style={{
            border: `1px solid ${surface.border}`,
            background: surface.card,
            color: text.muted,
          }}
        >
          {mode === "dark" ? <Sun size={15} aria-hidden="true" /> : <Moon size={15} aria-hidden="true" />}
        </button>
        <button
          type="button"
          aria-label="Abrir configurações"
          onClick={() => setSettingsOpen(true)}
          title="Abrir configurações"
          style={{
            padding: `${space.tight}px ${space.base}px`,
            border: `1px solid ${surface.border}`,
            borderRadius: 6,
            background: surface.card,
            color: text.muted,
            font: "inherit",
            fontSize: type.ui,
            cursor: "pointer",
          }}
        >
          <Settings2 size={15} aria-hidden="true" />
        </button>
      </header>

      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {goalsOpen && (
          <AsyncPanel loading={inspection.loading && !inspection.data} error={inspection.error} onRetry={inspection.reload}>
            <GoalSidebar goals={goals.data ?? []} selected={selectedGoal} onSelect={setSelectedGoal} />
          </AsyncPanel>
        )}

        <main role="tabpanel" id={`stage-panel-${stage}`} aria-labelledby={`stage-${stage}`} style={{ flex: 1, minWidth: 0, overflowY: "auto" }}>
          <ProjectModeBanner inspection={inspection.data} onAdapt={() => setAdaptationOpen(true)} />
          {stage === "attention" && (
            <AttentionStage
              inspection={inspection.data}
              goalsCount={goals.data?.length ?? 0}
              onOpenDefine={() => setStage("define")}
              onOpenPlan={() => setStage("plan")}
              onOpenRun={showRun}
              onAdapt={() => setAdaptationOpen(true)}
            />
          )}
          {stage === "define" && <DiscussScreen />}
          {stage === "plan" && <PlanScreen onRunStarted={showRun} />}
          {stage === "run" && <BuildScreen runId={runId} />}
          {stage === "review" && <ReviewScreen />}
          {stage === "knowledge" && (
            <>
              <ProjectScreen />
              <div style={{ padding: `0 ${space.wide} ${space.wide}px` }}><ProjectExplorer /></div>
            </>
          )}
        </main>

        {inspectorOpen && <Inspector goal={goal} onClose={() => setInspectorOpen(false)} />}
      </div>

      <RunStatusBar
        detail={run.data ?? null}
        epoch={projectEpoch}
        onCancel={() => void cancelRun()}
        onReveal={() => setStage("run")}
        onEngineChanged={() => setProjectEpoch((value) => value + 1)}
      />

      <AdaptationWizard
        inspection={inspection.data}
        autoOpen={adaptationOpen}
        onApplied={onAdaptationApplied}
      />

      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onChanged={() => setProjectEpoch((value) => value + 1)}
      />
    </div>
  );
};

export const Workspace: FC = () => (
  <ThemeProvider>
    <WorkspaceShell />
  </ThemeProvider>
);

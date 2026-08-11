import type { FC } from "react";
import { useCallback, useEffect, useState } from "react";
import { api, type GoalView } from "../api";
import { AsyncPanel } from "../components/Primitives";
import { desktop } from "../desktop";
import { useAsync, usePolling } from "../hooks/useAsync";
import { BuildScreen } from "../screens/BuildScreen";
import { PlanScreen } from "../screens/PlanScreen";
import { ProjectScreen } from "../screens/ProjectScreen";
import { ReviewScreen } from "../screens/ReviewScreen";
import { size, space, surface, text, type } from "../theme";
import { ChatStage } from "./ChatStage";
import { GoalSidebar } from "./GoalSidebar";
import { Inspector } from "./Inspector";
import { ProjectSwitcher } from "./ProjectSwitcher";
import { RunStatusBar } from "./RunStatusBar";

/**
 * The stages a Goal moves through, left to right.
 *
 * They are stages, not pages: the previous shell showed five equal tabs, which
 * said nothing about sequence, so nobody could tell what to do next. Docs is
 * last and is reference rather than a stage — it is here because it has to
 * live somewhere, and pretending it is part of the pipeline would be worse.
 */
export const STAGES = ["discuss", "plan", "build", "review", "docs"] as const;
export type Stage = (typeof STAGES)[number];

export const STAGE_LABELS: Record<Stage, string> = {
  discuss: "Discuss",
  plan: "Plan",
  build: "Build",
  review: "Review",
  docs: "Docs",
};

/** What each stage answers, shown under the tab so nobody has to guess. */
export const STAGE_PURPOSE: Record<Stage, string> = {
  discuss: "Decide what to build",
  plan: "See what a Goal will take",
  build: "Watch it happen",
  review: "Check it can be called done",
  docs: "Read what the project says",
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

export const Workspace: FC = () => {
  const [stage, setStage] = useState<Stage>("discuss");
  const [projectEpoch, setProjectEpoch] = useState(0);
  const [selectedGoal, setSelectedGoal] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [root, setRoot] = useState<string | null>(null);

  const goals = useAsync(() => api.goals(), [projectEpoch]);
  const run = useAsync(
    async () => (runId ? await api.run(runId) : null),
    [runId, projectEpoch],
  );

  const active = run.data ? ACTIVE_RUN_STATES.has(run.data.run.state) : false;
  usePolling(run.reload, Boolean(runId) && active, 900);

  // A failed first load retries itself.
  //
  // The engine is reported running as soon as its process survives startup,
  // which is a moment before it accepts connections — so the window loaded its
  // Goals, failed, and sat behind a red Retry box with a perfectly healthy
  // engine underneath. A shell that starts its own engine has to wait for it.
  usePolling(goals.reload, goals.error !== null, 1500);

  useEffect(() => {
    void desktop.projectRoot().then((value) => setRoot(value ?? null));
  }, [projectEpoch]);

  // A project that has just been opened has no selection yet; picking the
  // first Goal is better than an empty inspector nobody knows how to fill.
  useEffect(() => {
    if (selectedGoal === null && goals.data && goals.data.length > 0) {
      setSelectedGoal(goals.data[0].id);
    }
  }, [goals.data, selectedGoal]);

  const goal: GoalView | null =
    goals.data?.find((item) => item.id === selectedGoal) ?? null;

  const onProjectOpened = useCallback(() => {
    setSelectedGoal(null);
    setRunId(null);
    setSessionId(null);
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

  const startSession = useCallback(async () => {
    const created = await api.createDiscussion();
    setSessionId(created.sessionId);
    return created.sessionId;
  }, []);

  const showRun = useCallback((id: string) => {
    setRunId(id);
    setStage("build");
  }, []);

  const [keyboardMove, setKeyboardMove] = useState(false);

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const next = nextStageIndex(event.key, STAGES.indexOf(stage), STAGES.length);
      if (next === null) return;
      event.preventDefault();
      setStage(STAGES[next]);
      setKeyboardMove(true);
    },
    [stage],
  );

  // Focus moves after the render, not inside the handler.
  //
  // Focusing synchronously puts focus on a tab whose tabIndex is still -1,
  // under a panel that is being replaced; in the WebKit view every arrow key
  // after the first then did nothing. jsdom is forgiving enough not to catch
  // this, so the guard is here rather than in a test.
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
          gap: space.loose,
          padding: `0 ${space.base}px`,
          borderBottom: `1px solid ${surface.border}`,
          background: surface.chrome,
        }}
      >
        <ProjectSwitcher root={root} onOpened={onProjectOpened} />

        <div
          role="tablist"
          aria-label="Stages"
          onKeyDown={onKeyDown}
          style={{ display: "flex", gap: space.hair }}
        >
          {STAGES.map((key) => (
            <button
              key={key}
              role="tab"
              id={`stage-${key}`}
              aria-selected={stage === key}
              aria-controls={`stage-panel-${key}`}
              tabIndex={stage === key ? 0 : -1}
              title={STAGE_PURPOSE[key]}
              onClick={() => setStage(key)}
              style={{
                padding: `${space.tight}px ${space.base}px`,
                border: "none",
                borderRadius: 6,
                background: stage === key ? surface.card : "transparent",
                boxShadow: stage === key ? "inset 0 0 0 1px " + surface.border : "none",
                color: stage === key ? text.primary : text.muted,
                font: "inherit",
                fontSize: type.ui,
                fontWeight: stage === key ? 600 : 400,
                cursor: "pointer",
              }}
            >
              {STAGE_LABELS[key]}
            </button>
          ))}
        </div>

        <span style={{ marginLeft: "auto", color: text.faint, fontSize: type.small }}>
          {STAGE_PURPOSE[stage]}
        </span>
      </header>

      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <AsyncPanel loading={false} error={goals.error} onRetry={goals.reload}>
          <GoalSidebar
            goals={goals.data ?? []}
            selected={selectedGoal}
            onSelect={setSelectedGoal}
          />
        </AsyncPanel>

        <main
          role="tabpanel"
          id={`stage-panel-${stage}`}
          aria-labelledby={`stage-${stage}`}
          style={{ flex: 1, minWidth: 0, overflowY: "auto" }}
        >
          {stage === "discuss" && (
            <ChatStage
              sessionId={sessionId}
              goalIds={(goals.data ?? []).map((item) => item.id)}
              onRunStarted={showRun}
              onSelectGoal={setSelectedGoal}
              onCancel={cancelRun}
              onStartSession={startSession}
            />
          )}
          {stage === "plan" && <PlanScreen onRunStarted={showRun} />}
          {stage === "build" && <BuildScreen runId={runId} />}
          {stage === "review" && <ReviewScreen />}
          {stage === "docs" && <ProjectScreen />}
        </main>

        <Inspector goal={goal} />
      </div>

      <RunStatusBar
        detail={run.data ?? null}
        epoch={projectEpoch}
        onCancel={() => void cancelRun()}
        onReveal={() => setStage("build")}
        onEngineChanged={() => setProjectEpoch((value) => value + 1)}
      />
    </div>
  );
};

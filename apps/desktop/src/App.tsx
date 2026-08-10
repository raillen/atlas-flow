import { useCallback, useRef, useState } from "react";
import { AtlasLogo } from "@atlas-flow/ui";
import { DiscussScreen } from "./screens/DiscussScreen";
import { PlanScreen } from "./screens/PlanScreen";
import { BuildScreen } from "./screens/BuildScreen";
import { ReviewScreen } from "./screens/ReviewScreen";
import { ProjectScreen } from "./screens/ProjectScreen";

export const TABS = ["discuss", "plan", "build", "review", "project"] as const;
export type Tab = (typeof TABS)[number];

const LABELS: Record<Tab, string> = {
  discuss: "Discuss",
  plan: "Plan",
  build: "Build",
  review: "Review",
  project: "Project",
};

/**
 * Arrow keys move between tabs, Home/End jump to the ends.
 *
 * This is the WAI-ARIA tabs pattern: a tablist is one stop in the tab order and
 * the arrow keys move within it, so reaching the fifth tab does not mean
 * pressing Tab five times.
 */
export function nextTabIndex(key: string, current: number, count: number): number | null {
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

const shellStyle: React.CSSProperties = {
  fontFamily: "system-ui, sans-serif",
  height: "100dvh",
  display: "flex",
  flexDirection: "column",
  background: "#f8fafc",
  color: "#0f172a",
};

const navStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.25rem",
  padding: "0.5rem 1rem",
  borderBottom: "1px solid #e2e8f0",
  background: "white",
};

const tabBase: React.CSSProperties = {
  padding: "0.5rem 1rem",
  border: "none",
  borderRadius: 6,
  background: "transparent",
  cursor: "pointer",
  fontSize: "0.85rem",
  fontWeight: 500,
  color: "#475569",
};

const tabActive: React.CSSProperties = {
  ...tabBase,
  background: "#6366f1",
  color: "white",
};

export function App() {
  const [tab, setTab] = useState<Tab>("plan");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const onRunStarted = useCallback((runId: string) => {
    setActiveRunId(runId);
    setTab("build");
  }, []);

  const onKeyDown = useCallback((event: React.KeyboardEvent) => {
    const current = TABS.indexOf(tab);
    const next = nextTabIndex(event.key, current, TABS.length);
    if (next === null) return;
    event.preventDefault();
    setTab(TABS[next]);
    tabRefs.current[next]?.focus();
  }, [tab]);

  return (
    <div style={shellStyle}>
      <nav style={navStyle}>
        <AtlasLogo size={20} />
        <span style={{ fontWeight: 700, marginRight: "1rem", marginLeft: "0.5rem" }}>
          Atlas Flow
        </span>
        <div role="tablist" aria-label="Workspace modes" onKeyDown={onKeyDown}
             style={{ display: "flex", gap: "0.25rem" }}>
          {TABS.map((key, index) => (
            <button
              key={key}
              ref={(node) => { tabRefs.current[index] = node; }}
              role="tab"
              id={`tab-${key}`}
              aria-selected={tab === key}
              aria-controls={`panel-${key}`}
              tabIndex={tab === key ? 0 : -1}
              style={tab === key ? tabActive : tabBase}
              onClick={() => setTab(key)}
            >
              {LABELS[key]}
            </button>
          ))}
        </div>
      </nav>

      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        style={{ flex: 1, overflowY: "auto" }}
      >
        {tab === "discuss" && (
          <DiscussScreen
            sessionId={crypto.randomUUID().slice(0, 8)}
            serverUrl="ws://localhost:8000"
          />
        )}
        {tab === "plan" && <PlanScreen onRunStarted={onRunStarted} />}
        {tab === "build" && <BuildScreen runId={activeRunId} />}
        {tab === "review" && <ReviewScreen />}
        {tab === "project" && <ProjectScreen />}
      </div>
    </div>
  );
}

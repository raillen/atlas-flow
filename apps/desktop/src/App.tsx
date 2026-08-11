import { useCallback, useEffect, useRef, useState } from "react";
import { AtlasLogo } from "@atlas-flow/ui";
import { DiscussScreen } from "./screens/DiscussScreen";
import { PlanScreen } from "./screens/PlanScreen";
import { BuildScreen } from "./screens/BuildScreen";
import { ReviewScreen } from "./screens/ReviewScreen";
import { ProjectScreen } from "./screens/ProjectScreen";
import { accent, surface, text } from "./theme";

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
  background: surface.raised,
  color: text.primary,
};

const navStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.25rem",
  padding: "0.5rem 1rem",
  borderBottom: `1px solid ${surface.border}`,
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
  color: text.muted,
};

const tabActive: React.CSSProperties = {
  ...tabBase,
  background: accent.base,
  color: "white",
};

export function App() {
  const [tab, setTab] = useState<Tab>("plan");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  // Focus follows the selection only when the keyboard moved it; stealing
  // focus on mount, or when a click already moved it, is its own bug.
  const keyboardNavigation = useRef(false);

  const onRunStarted = useCallback((runId: string) => {
    setActiveRunId(runId);
    setTab("build");
  }, []);

  const onKeyDown = useCallback((event: React.KeyboardEvent) => {
    const current = TABS.indexOf(tab);
    const next = nextTabIndex(event.key, current, TABS.length);
    if (next === null) return;
    event.preventDefault();
    keyboardNavigation.current = true;
    setTab(TABS[next]);
  }, [tab]);

  /**
   * Move focus after the render, not during the handler.
   *
   * Focusing synchronously put focus on a tab whose `tabIndex` was still -1
   * from the previous render, and the panel swapping underneath took it away
   * again — so exactly one arrow key worked and every one after it went
   * nowhere. Arrow navigation that only moves once is worse than none: it
   * looks supported until somebody relies on it.
   */
  useEffect(() => {
    if (!keyboardNavigation.current) return;
    keyboardNavigation.current = false;
    tabRefs.current[TABS.indexOf(tab)]?.focus();
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
        {tab === "discuss" && <DiscussScreen />}
        {tab === "plan" && <PlanScreen onRunStarted={onRunStarted} />}
        {tab === "build" && <BuildScreen runId={activeRunId} />}
        {tab === "review" && <ReviewScreen />}
        {tab === "project" && <ProjectScreen />}
      </div>
    </div>
  );
}

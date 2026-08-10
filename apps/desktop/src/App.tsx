import { useCallback, useState } from "react";
import { AtlasLogo } from "@atlas-flow/ui";
import { DiscussScreen } from "./screens/DiscussScreen";
import {
  BuildScreen,
  PlanScreen,
  ProjectScreen,
  ReviewScreen,
} from "./screens/DesktopModes";

type Tab = "discuss" | "plan" | "build" | "review" | "project";

const tabs: { key: Tab; label: string }[] = [
  { key: "discuss", label: "Discuss" },
  { key: "plan", label: "Plan" },
  { key: "build", label: "Build" },
  { key: "review", label: "Review" },
  { key: "project", label: "Project" },
];

const shellStyle: React.CSSProperties = {
  fontFamily: "system-ui, sans-serif",
  height: "100dvh",
  display: "flex",
  flexDirection: "column",
};

const navStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.25rem",
  padding: "0.5rem 1rem",
  borderBottom: "1px solid #e2e8f0",
  background: "#f8fafc",
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

const contentStyle: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
};

export function App() {
  const [tab, setTab] = useState<Tab>("discuss");

  const renderTab = useCallback(() => {
    switch (tab) {
      case "discuss":
        return (
          <DiscussScreen
            sessionId={crypto.randomUUID().slice(0, 8)}
            serverUrl="ws://localhost:8000"
          />
        );
      case "plan":
        return <PlanScreen />;
      case "build":
        return <BuildScreen />;
      case "review":
        return <ReviewScreen />;
      case "project":
        return <ProjectScreen />;
    }
  }, [tab]);

  return (
    <div style={shellStyle}>
      <nav style={navStyle} role="tablist">
        <AtlasLogo size={20} />
        <span style={{ fontWeight: 700, marginRight: "1rem", marginLeft: "0.5rem" }}>
          Atlas Flow
        </span>
        {tabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            style={tab === t.key ? tabActive : tabBase}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div style={contentStyle}>{renderTab()}</div>
    </div>
  );
}

import type { FC } from "react";

const section = { padding: "2rem" } as const;
const titleStyle = { fontSize: "1.25rem", fontWeight: 700, marginBottom: "1rem" } as const;
const card = { padding: "1rem", border: "1px solid #e2e8f0", borderRadius: 8, marginBottom: "0.5rem" } as const;

export const PlanScreen: FC = () => (
  <div style={section}>
    <h2 style={titleStyle}>Plan</h2>
    <div style={card}>
      <strong>Goal: P06-G01 — Desktop Modes</strong>
      <p style={{ color: "#64748b", marginTop: "0.25rem" }}>4 tasks planned • 0 running</p>
    </div>
    <div style={card}>
      <strong>✏️ Write DiscussScreen</strong>
      <span style={{ marginLeft: "0.5rem", color: "#059669" }}>done</span>
      <p style={{ color: "#94a3b8", fontSize: "0.8rem" }}>apps/desktop/src/screens</p>
    </div>
    <div style={card}>
      <strong>✏️ Add tab navigation</strong>
      <span style={{ marginLeft: "0.5rem", color: "#f59e0b" }}>ready</span>
      <p style={{ color: "#94a3b8", fontSize: "0.8rem" }}>apps/desktop/src/App.tsx</p>
    </div>
    <div style={card}>
      <strong>📄 Build mode shell</strong>
      <span style={{ marginLeft: "0.5rem", color: "#94a3b8" }}>pending</span>
    </div>
  </div>
);

export const BuildScreen: FC = () => (
  <div style={section}>
    <h2 style={titleStyle}>Build</h2>
    <div style={card}>
      <strong>🔨 Current task: tab navigation</strong>
      <p style={{ color: "#64748b" }}>
        Runner: DummyRunner • Model: MiMo V2.5 Pro • Status: running
      </p>
    </div>
    <div style={card}>
      <details>
        <summary style={{ cursor: "pointer" }}>Task log (last 3 events)</summary>
        <pre style={{ fontSize: "0.8rem", color: "#475569", marginTop: "0.25rem" }}>
          atlas.task.ready   tab-navigation
          atlas.task.running tab-navigation
          atlas.attempt.started DummyRunner | mimo
        </pre>
      </details>
    </div>
  </div>
);

export const ReviewScreen: FC = () => (
  <div style={section}>
    <h2 style={titleStyle}>Review</h2>
    <div style={card}>
      <strong>Gate: build</strong>
      <span style={{ marginLeft: "0.5rem", color: "#059669" }}>PASS</span>
      <p style={{ color: "#94a3b8", fontSize: "0.8rem" }}>tsc + eslint + vitest</p>
    </div>
    <div style={card}>
      <strong>Gate: tests</strong>
      <span style={{ marginLeft: "0.5rem", color: "#059669" }}>PASS</span>
      <p style={{ color: "#94a3b8", fontSize: "0.8rem" }}>65 pytest + 5 vitest</p>
    </div>
    <div style={card}>
      <strong>Gate: review</strong>
      <span style={{ marginLeft: "0.5rem", color: "#f59e0b" }}>PENDING</span>
      <p style={{ color: "#94a3b8", fontSize: "0.8rem" }}>Cross-provider review requested</p>
    </div>
    <div style={card}>
      <strong>Evidence</strong>
      <p style={{ color: "#94a3b8", fontSize: "0.8rem" }}>
        2 CI checks attached • 1 review pending
      </p>
    </div>
  </div>
);

export const ProjectScreen: FC = () => (
  <div style={section}>
    <h2 style={titleStyle}>Project</h2>
    <div style={card}>
      <strong>Atlas Flow v0.1.0</strong>
      <p style={{ color: "#64748b" }}>Framework: project-atlas-framework 0.1.0</p>
    </div>
    <div style={card}>
      <strong>Phases</strong>
      <ul style={{ paddingLeft: "1.25rem", margin: "0.25rem 0" }}>
        <li>P00 — Foundation ✓</li>
        <li>P01 — Project Atlas Integration ✓</li>
        <li>P02 — Discuss & Decisions ✓</li>
        <li>P03 — Orchestration Runtime ✓</li>
        <li>P04 — Atlas Harness ✓</li>
        <li>P05 — Planner & DAG ✓</li>
        <li>P06 — Desktop Modes (current)</li>
        <li>P07 — Verification ✓</li>
        <li>P08 — Model Routing ✓</li>
        <li>P09 — Hardening</li>
        <li>P10 — Beta Release</li>
      </ul>
    </div>
    <div style={card}>
      <strong>Agents</strong>
      <span style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
        {" "}chief-architect, goal-planner, core-implementer, ui-engineer, repo-explorer,
        tester, security-reviewer, release-verifier…
      </span>
    </div>
  </div>
);

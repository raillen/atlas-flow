// @vitest-environment jsdom
/**
 * Accessibility audit over the rendered DOM.
 *
 * The contrast checks in theme.test.ts look at tokens; these look at what a
 * screen reader and a keyboard actually meet. A palette can be perfect while
 * the markup is unusable, so both are needed and neither substitutes for the
 * other.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";

import { App } from "./App";
import { DiscussScreen } from "./screens/DiscussScreen";
import { PlanScreen } from "./screens/PlanScreen";
import { BuildScreen } from "./screens/BuildScreen";
import { ReviewScreen } from "./screens/ReviewScreen";
import { ProjectScreen } from "./screens/ProjectScreen";

const GOALS = [
  {
    id: "P01-G01",
    phase: "P01",
    title: "Project Atlas Integration",
    state: "ACTIVE",
    objective: "Read the canonical manifests",
    acceptance: ["Loads manifests", "Rejects incompatible versions"],
    gates: { build: "required", tests: "required", review: "required", documentation: "required" },
    dependencies: [],
    evidence_count: 0,
  },
];

const RUN = {
  id: "run-1",
  goal_id: "P01-G01",
  goal_revision: "abc",
  state: "VERIFYING",
  autonomy: "agentic",
  created_at: "2026-08-11T00:00:00Z",
  task_count: 1,
};

const RUN_DETAIL = {
  run: RUN,
  tasks: [
    {
      id: "task-1",
      objective: "Loads manifests",
      state: "SUCCEEDED",
      role: "core-implementer",
      risk: "medium",
      scope: [],
      dependencies: [],
    },
  ],
  attempts: [
    {
      id: "att-1",
      task_id: "task-1",
      runner: "dummy",
      model_id: "xiaomi/mimo-v2.5-pro",
      state: "COMPLETED",
      started_at: "2026-08-11T00:00:01Z",
      completed_at: "2026-08-11T00:00:02Z",
      error_msg: null,
    },
  ],
  events: [
    {
      id: "evt-1",
      timestamp: "2026-08-11T00:00:01Z",
      type: "atlas.run.started",
      project_id: "atlas-flow",
      run_id: "run-1",
      payload: {},
    },
  ],
};

const VERIFICATION = {
  goal_id: "P01-G01",
  gates: [
    { gate: "build", requirement: "required", verdict: "PASSED", evidence_ids: [], details: "" },
    { gate: "tests", requirement: "required", verdict: "PENDING", evidence_ids: [], details: "no evidence attached" },
  ],
  evidence: [
    {
      id: "ev-1",
      gate: "build",
      kind: "runner_result",
      verdict: "PASSED",
      uri: "attempt att-1 completed",
      task_id: "task-1",
      attached_at: "2026-08-11T00:00:02Z",
    },
  ],
  completable: false,
  blocking: "P01-G01: no passing evidence for required gate(s): tests",
};

const ROUTING = {
  state: "reachable",
  reachable: true,
  degraded: false,
  reason: "3 model(s) reported by the live registry",
  probed_at: "2026-08-11T00:00:00Z",
  available: ["deepseek/deepseek-v4-pro"],
  roles: [
    {
      role: "reviewer",
      selected: "deepseek-v4-pro",
      provider: "deepseek",
      explanation: "Role 'reviewer' routed to deepseek-v4-pro",
      fallback_attempts: 0,
    },
  ],
  stats: [
    {
      model_key: "deepseek-v4-pro",
      uses: 2,
      successes: 2,
      failures: 0,
      success_rate: 1,
      average_latency_ms: 120,
    },
  ],
};

const PROJECT = {
  id: "atlas-flow",
  types: ["agent-orchestrator"],
  phases: 11,
  agents: ["goal-planner"],
  skills: ["goal-contracts"],
  runners: ["cmd", "dummy"],
};

const DOCS = [{ path: "01-architecture/GOAL_ENGINE.md", title: "Goal Engine", section: "Architecture" }];

const DISCUSSION = {
  id: "session-1",
  project_id: "atlas-flow",
  title: "Kickoff",
  messages: [
    { id: "m1", timestamp: "2026-08-11T00:00:00Z", content: "Hello", turn_type: "message" },
  ],
  decisions: [
    {
      id: "d1",
      title: "Use SQLite",
      statement: "Operational state goes in SQLite",
      rationale: "",
      status: "PROPOSED",
      affected_domains: [],
      requires_adr: true,
      timestamp: "2026-08-11T00:00:01Z",
    },
  ],
  draft: {
    product: "sufficient", architecture: "partial", ux: "unknown", data: "unknown",
    security: "unknown", quality: "unknown", operations: "unknown",
    ai_orchestration: "unknown", roadmap: "unknown",
  },
  started_at: "2026-08-11T00:00:00Z",
};

function respond(url: string): unknown {
  if (url.endsWith("/api/project/inspection")) return {
    root: "/tmp/project", mode: "atlas-ready", project_id: "atlas-flow", project_name: "Atlas Flow", types: ["agent-orchestrator"], framework_name: "project-atlas-framework", framework_version: "0.1.0", framework_supported: true, git_present: true, missing_manifests: [], invalid_manifests: [], reason: "ready", recommendation: "ready", capabilities: { can_explore: true, can_discuss: true, can_adapt: false, can_plan: true, can_run: true, can_review: true },
  };
  if (url.endsWith("/api/goals")) return GOALS;
  if (url.includes("/verification")) return VERIFICATION;
  if (url.endsWith("/api/routing")) return ROUTING;
  if (url.endsWith("/api/runs")) return [RUN];
  if (url.includes("/api/runs/")) return RUN_DETAIL;
  if (url.endsWith("/api/project")) return PROJECT;
  if (url.endsWith("/api/discussions")) return ["session-1"];
  if (url.includes("/api/discussions/")) return DISCUSSION;
  if (url.endsWith("/api/docs")) return DOCS;
  if (url.includes("/api/docs/")) return { path: DOCS[0].path, content: "# Goal Engine\n" };
  return {};
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => ({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => respond(String(input)),
    })),
  );
  // The Discuss screen opens a socket; jsdom has none.
  vi.stubGlobal(
    "WebSocket",
    class {
      readyState = 0;
      close() {}
      send() {}
    },
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** Serious and critical violations only: those are the ones that block use. */
async function violations(container: HTMLElement): Promise<string[]> {
  const results = await axe.run(container, {
    resultTypes: ["violations"],
    rules: { "color-contrast": { enabled: false } }, // covered by theme.test.ts
  });
  return results.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => `${violation.id}: ${violation.help}`);
}

describe("rendered accessibility", () => {
  it("the shell has no serious or critical violations", async () => {
    const { container } = render(<App />);
    await waitFor(() => expect(screen.getByRole("tablist")).toBeTruthy());

    expect(await violations(container)).toEqual([]);
  }, 15000);

  it("only the selected tab is in the tab order", async () => {
    render(<App />);
    const tabs = await screen.findAllByRole("tab");

    const reachable = tabs.filter((tab) => tab.getAttribute("tabindex") === "0");
    expect(reachable).toHaveLength(1);
    expect(reachable[0].getAttribute("aria-selected")).toBe("true");
  });

  it("the tab panel is labelled by its tab", async () => {
    render(<App />);
    const panel = await screen.findByRole("tabpanel");

    const labelledBy = panel.getAttribute("aria-labelledby");
    expect(labelledBy).toBeTruthy();
    expect(document.getElementById(labelledBy!)?.getAttribute("role")).toBe("tab");
  });

  it("can collapse and reopen the persistent side panels", async () => {
    render(<App />);

    const goalsToggle = await screen.findByRole("button", { name: "Recolher painel de Goals" });
    expect(goalsToggle.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(goalsToggle);
    expect(screen.getByRole("button", { name: "Expandir painel de Goals" }).getAttribute("aria-expanded")).toBe("false");

    const detailsToggle = screen.getByRole("button", { name: "Expandir painel de detalhes" });
    fireEvent.click(detailsToggle);
    expect(await screen.findByRole("complementary", { name: "Goal details" })).toBeTruthy();
  });

  it.each([
    ["Discuss", <DiscussScreen key="discuss" />],
    ["Plan", <PlanScreen key="plan" onRunStarted={() => {}} />],
    ["Build", <BuildScreen key="build" runId="run-1" />],
    ["Review", <ReviewScreen key="review" />],
    ["Project", <ProjectScreen key="project" />],
  ])("%s has no serious or critical violations", async (_name, element) => {
    const { container } = render(element);
    await waitFor(() => expect(container.querySelector("h2")).toBeTruthy());

    expect(await violations(container)).toEqual([]);
  });

  it("a live region announces a run while it is active", async () => {
    const { container } = render(<BuildScreen runId="run-1" />);
    await waitFor(() => expect(container.querySelector("h2")).toBeTruthy());

    expect(container.querySelector("[aria-live]")).toBeTruthy();
  });

  it("every interactive control has an accessible name", async () => {
    const { container } = render(<ReviewScreen />);
    await waitFor(() => expect(container.querySelector("h2")).toBeTruthy());

    for (const button of Array.from(container.querySelectorAll("button"))) {
      const name = button.textContent?.trim() || button.getAttribute("aria-label");
      expect(name, `button with no accessible name: ${button.outerHTML}`).toBeTruthy();
    }
  });
});

describe("the audit itself", () => {
  it("runs against React's development build", () => {
    // The production build does not export `act`, so an ambient
    // NODE_ENV=production fails every test here with a message that says
    // nothing about the cause. vitest.config.ts pins it; this notices if that
    // pin is ever removed.
    // `import.meta.env` is Vite's view of the same thing, and needs no Node
    // type definitions in a browser-targeted project.
    expect(import.meta.env.MODE).toBe("test");
  });

  it("detects a violation when there is one", async () => {
    // Without this, a silent misconfiguration of axe would make every check
    // above pass by finding nothing at all.
    const { container } = render(
      <div>
        <img src="x.png" />
        <div role="button" tabIndex={0} />
      </div>,
    );

    const found = await violations(container);
    expect(found.length).toBeGreaterThan(0);
    expect(found.join(" ")).toContain("image");
  });
});

describe("keyboard navigation between tabs", () => {
  it("keeps focus on the tablist so arrows can be pressed more than once", async () => {
    // This asserts the contract: after an arrow key, focus is on the newly
    // selected tab, so the next arrow key has somewhere to go.
    //
    // It does NOT reproduce the bug that motivated the fix. In the real
    // WebKit view, focusing synchronously inside the handler put focus on a
    // tab whose tabIndex was still -1, under a panel being replaced, and every
    // arrow key after the first did nothing. jsdom is forgiving enough that
    // this test passes either way — only the packaged smoke test catches it,
    // which is the whole reason that smoke test exists.
    render(<App />);
    const tabs = await screen.findAllByRole("tab");
    const selected = tabs.find((tab) => tab.getAttribute("aria-selected") === "true");
    expect(selected).toBeTruthy();
    selected!.focus();

    fireEvent.keyDown(selected!, { key: "ArrowRight" });
    await waitFor(() =>
      expect(document.activeElement?.getAttribute("aria-selected")).toBe("true"),
    );
    const afterOne = document.activeElement;

    fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
    await waitFor(() => expect(document.activeElement).not.toBe(afterOne));
    expect(document.activeElement?.getAttribute("role")).toBe("tab");
    expect(document.activeElement?.getAttribute("aria-selected")).toBe("true");
  });

  it("does not steal focus when nothing asked it to", async () => {
    render(<App />);
    await screen.findAllByRole("tab");

    expect(document.activeElement?.tagName).toBe("BODY");
  });
});

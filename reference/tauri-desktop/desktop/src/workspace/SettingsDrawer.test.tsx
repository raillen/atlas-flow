// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";

import { SettingsDrawer } from "./SettingsDrawer";

const SETTINGS_DOCUMENT = {
  settings: [
    {
      key: "autonomy_mode",
      value: "agentic",
      default: "agentic",
      source: { value: "project", scope: "project", environment_variable: "ATLAS_FLOW_AUTONOMY" },
      restart_required: true,
      applies_to: "new plans and runs",
      description: "Default autonomy policy.",
      kind: "select",
    },
    {
      key: "max_parallel_tasks",
      value: 4,
      default: 4,
      source: { value: "default", scope: "project", environment_variable: null },
      restart_required: false,
      applies_to: "new plans and runs",
      description: "How many tasks may run at once.",
      kind: "integer",
    },
    {
      key: "command_code_timeout_seconds",
      value: 600,
      default: 600,
      source: { value: "default", scope: "user", environment_variable: null },
      restart_required: false,
      applies_to: "command-code sessions",
      description: "How long a session may run.",
      kind: "integer",
    },
  ],
  providers: [
    {
      key: "deepseek-v4-pro",
      provider: "deepseek",
      command_code_id: "deepseek/deepseek-v4-pro",
      priority: "primary",
      availability: "expected",
      credential_ref: null,
      credential_configured: false,
    },
  ],
  mcp: { enabled: false, servers: [], skipped: {} },
  diagnostics: { projectRoot: "/tmp/project", projectMode: "atlas-ready", engineUrl: "http://localhost:8000" },
  restart_required: false,
  restart_reason: null,
};

const calls: { method: string; url: string; body?: unknown }[] = [];

beforeEach(() => {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = String(input);
      calls.push({ method: init?.method ?? "GET", url, body: init?.body });
      const respond = (payload: unknown) => ({
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => payload,
      });
      if (url.endsWith("/api/settings") && (init?.method === undefined || init.method === "GET")) {
        return respond(SETTINGS_DOCUMENT);
      }
      if (url.endsWith("/api/settings") && init?.method === "PUT") {
        return respond({ ...SETTINGS_DOCUMENT, changed: ["autonomy_mode"], written_paths: [] });
      }
      return respond({});
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function violations(container: HTMLElement): Promise<string[]> {
  const results = await axe.run(container, {
    resultTypes: ["violations"],
    rules: { "color-contrast": { enabled: false } },
  });
  return results.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => `${violation.id}: ${violation.help}`);
}

describe("SettingsDrawer", () => {
  it("loads and groups settings by scope", async () => {
    render(<SettingsDrawer open onClose={() => {}} onChanged={() => {}} />);

    expect(await screen.findByText("Settings")).toBeTruthy();
    expect(await screen.findByText("project settings")).toBeTruthy();
    expect(await screen.findByText("user settings")).toBeTruthy();

    expect(screen.getAllByText("autonomy mode").length).toBeGreaterThan(0);
    expect(screen.getAllByText("max parallel tasks").length).toBeGreaterThan(0);
    expect(screen.getAllByText("command code timeout seconds").length).toBeGreaterThan(0);
  });

  it("renders nothing when closed", () => {
    const { container } = render(<SettingsDrawer open={false} onClose={() => {}} onChanged={() => {}} />);
    expect(container.querySelector("[role=dialog]")).toBeNull();
  });

  it("saves the edited draft to the owning scope", async () => {
    render(<SettingsDrawer open onClose={() => {}} onChanged={() => {}} />);
    await screen.findByText("project settings");

    // The project scope holds autonomy_mode (select), max_parallel_tasks (integer) and
    // command_code_timeout_seconds is user scope — so two Save buttons exist.
    const saveButtons = screen.getAllByRole("button", { name: "Save" });
    expect(saveButtons).toHaveLength(2);

    fireEvent.click(saveButtons[0]);

    await waitFor(() => {
      const put = calls.find((call) => call.method === "PUT" && call.url.endsWith("/api/settings"));
      expect(put).toBeTruthy();
      const body = JSON.parse(String(put!.body)) as { scope: string; values: Record<string, unknown> };
      expect(body.scope).toBe("project");
      expect(body.values.autonomy_mode).toBe("agentic");
      expect(body.values.max_parallel_tasks).toBe(4);
      expect(Object.keys(body.values)).not.toContain("command_code_timeout_seconds");
    });
  });

  it("reports restart requirements from the save result", async () => {
    render(<SettingsDrawer open onClose={() => {}} onChanged={() => {}} />);
    await screen.findByText("project settings");

    fireEvent.click(screen.getAllByRole("button", { name: "Save" })[0]);

    expect(await screen.findByText(/Saved 1 setting/)).toBeTruthy();
  });

  it("shows providers and diagnostics", async () => {
    render(<SettingsDrawer open onClose={() => {}} onChanged={() => {}} />);

    expect(await screen.findByText("Model providers")).toBeTruthy();
    expect(await screen.findByText("deepseek/deepseek-v4-pro")).toBeTruthy();
    expect(await screen.findByText("Diagnostics")).toBeTruthy();
    expect(await screen.findByText("/tmp/project")).toBeTruthy();
  });

  it("has no serious or critical accessibility violations", async () => {
    const { container } = render(<SettingsDrawer open onClose={() => {}} onChanged={() => {}} />);
    await screen.findByText("project settings");

    expect(await violations(container)).toEqual([]);
  }, 15000);
});

// @vitest-environment jsdom
/**
 * What the chat does, not what the parser returns.
 *
 * commands.test.ts already covers the parsing. These tests exist because the
 * dangerous failure is one level up: a sentence that merely mentions a verb
 * must not reach the API, and a command must not be quietly filed away as
 * conversation. Both are invisible to a parser test.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ChatStage } from "./ChatStage";

const calls: { url: string; method: string; body: unknown }[] = [];

function respond(url: string): unknown {
  if (url.includes("/verification")) {
    return {
      goal_id: "P01-G01",
      gates: [
        { gate: "build", requirement: "required", verdict: "PASSED", evidence_ids: [], details: "" },
        { gate: "tests", requirement: "required", verdict: "PENDING", evidence_ids: [], details: "" },
      ],
      evidence: [],
      completable: false,
      blocking: "P01-G01: no passing evidence for required gate(s): tests",
    };
  }
  if (url.includes("/api/runs")) {
    return {
      id: "run-7",
      goal_id: "P01-G01",
      goal_revision: "abc",
      state: "PLANNING",
      autonomy: "agentic",
      created_at: "2026-08-11T00:00:00Z",
      task_count: 0,
    };
  }
  return {};
}

beforeEach(() => {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({
        url: String(input),
        method: init?.method ?? "GET",
        body: init?.body ? JSON.parse(String(init.body)) : null,
      });
      return {
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => respond(String(input)),
      };
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

interface Harness {
  runs: string[];
  selected: string[];
  cancels: number;
}

function mount(goalIds: string[] = ["P01-G01"]): Harness {
  const harness: Harness = { runs: [], selected: [], cancels: 0 };
  render(
    <ChatStage
      sessionId="session-1"
      goalIds={goalIds}
      onRunStarted={(id) => harness.runs.push(id)}
      onSelectGoal={(id) => harness.selected.push(id)}
      onCancel={async () => {
        harness.cancels += 1;
        return "Asked run-7 to stop.";
      }}
      onStartSession={async () => "session-1"}
    />,
  );
  return harness;
}

function type(value: string): void {
  const input = screen.getByLabelText("Message or command");
  fireEvent.change(input, { target: { value } });
  fireEvent.keyDown(input, { key: "Enter" });
}

describe("commands act", () => {
  it("run starts a run and offers to watch it", async () => {
    const harness = mount();
    type("run P01-G01");

    await waitFor(() => expect(harness.runs).toEqual(["run-7"]));
    expect(await screen.findByText(/Started run-7 for P01-G01/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Watch it" })).toBeTruthy();
  });

  it("refuses a Goal this project does not have, without calling the API", async () => {
    const harness = mount(["P01-G01"]);
    type("run P99-G01");

    expect(await screen.findByText(/no Goal P99-G01/)).toBeTruthy();
    expect(harness.runs).toEqual([]);
    expect(calls.filter((call) => call.method === "POST")).toEqual([]);
  });

  it("cancel delegates to the run in flight", async () => {
    const harness = mount();
    type("cancel");

    await waitFor(() => expect(harness.cancels).toBe(1));
    expect(await screen.findByText(/Asked run-7 to stop/)).toBeTruthy();
  });

  it("evidence reports each gate's verdict", async () => {
    mount();
    type("evidence P01-G01");

    expect(await screen.findByText(/no passing evidence for required gate/)).toBeTruthy();
    expect(screen.getByText(/tests: PENDING/)).toBeTruthy();
  });

  it("help lists what can be typed", async () => {
    mount();
    type("help");

    // Two copies: the empty-state hint and the answer. Either proves the point.
    await waitFor(() => expect(screen.getAllByText(/cancel — Stop the run/).length).toBeGreaterThan(0));
  });
});

describe("conversation is not a command", () => {
  it("a sentence that mentions cancelling cancels nothing", async () => {
    const harness = mount();
    type("I think we should cancel the retry policy");

    await waitFor(() => expect(screen.getByText(/Kept in the discussion/)).toBeTruthy());
    expect(harness.cancels).toBe(0);
    const posted = calls.find((call) => call.method === "POST");
    expect(posted?.url).toContain("/messages");
    expect(posted?.body).toMatchObject({
      content: "I think we should cancel the retry policy",
    });
  });

  it("a verb with no Goal is a message, not a half-command", async () => {
    const harness = mount();
    type("run the whole thing past me first");

    await waitFor(() => expect(screen.getByText(/Kept in the discussion/)).toBeTruthy());
    expect(harness.runs).toEqual([]);
  });
});

describe("the transcript", () => {
  it("shows who said what", async () => {
    mount();
    type("help");

    expect(await screen.findByText("You")).toBeTruthy();
    expect(await screen.findByText("Atlas Flow")).toBeTruthy();
  });

  it("reports a failure instead of swallowing it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => ({ detail: "budget exhausted" }),
      })),
    );
    mount();
    type("run P01-G01");

    expect(await screen.findByText(/budget exhausted|500/)).toBeTruthy();
  });
});

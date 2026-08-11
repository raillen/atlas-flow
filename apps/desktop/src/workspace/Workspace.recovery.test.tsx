// @vitest-environment jsdom
/**
 * The window heals when the engine finally answers.
 *
 * Found by launching the packaged app, not by any gate: the shell starts its
 * own engine and reports it running as soon as the process survives startup,
 * which is a moment before it accepts connections. The first load of the Goals
 * therefore failed, and the sidebar sat behind a red Retry box with a
 * perfectly healthy engine underneath it. Nothing in the suite noticed.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";

import { Workspace } from "./Workspace";

const GOALS = [
  {
    id: "P01-G01",
    phase: "P01",
    title: "Project Atlas Integration",
    state: "ACTIVE",
    objective: "Read the canonical manifests",
    acceptance: ["Loads manifests"],
    gates: { build: "required", tests: "required", review: "required", documentation: "required" },
    dependencies: [],
    evidence_count: 0,
  },
];

function respond(url: string): unknown {
  if (url.endsWith("/api/goals")) return GOALS;
  if (url.includes("/verification")) {
    return {
      goal_id: "P01-G01",
      gates: [
        { gate: "build", requirement: "required", verdict: "PENDING", evidence_ids: [], details: "" },
      ],
      evidence: [],
      completable: false,
      blocking: "P01-G01: no passing evidence for required gate(s): build",
    };
  }
  return {};
}

/** Refuses every request until `up` is flipped, like an engine still binding. */
function engineComingUp(): { start: () => void } {
  let up = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      if (!up) throw new TypeError("Failed to fetch");
      return {
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => respond(String(input)),
      };
    }),
  );
  return {
    start: () => {
      up = true;
    },
  };
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
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
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("a failed first load", () => {
  it("recovers on its own once the engine answers", async () => {
    const engine = engineComingUp();
    render(<Workspace />);

    // The engine is not up yet, so the Goals cannot load.
    await waitFor(() => expect(screen.getByRole("button", { name: /retry/i })).toBeTruthy());

    engine.start();

    // Time is advanced rather than waited out: a test that depends on the
    // wall clock is a test that fails on a loaded machine for no reason.
    // Nobody presses Retry — the window is expected to notice by itself.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    await waitFor(() => expect(screen.getByText("P01-G01")).toBeTruthy());
    expect(screen.queryByRole("button", { name: /retry/i })).toBeNull();
  });
});

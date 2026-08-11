import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./api";

function mockResponse(body: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    statusText: "Error",
    json: async () => body,
  } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("converts snake_case fields to camelCase", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        mockResponse([
          {
            id: "run-1",
            goal_id: "P01-G01",
            goal_revision: "abc",
            state: "RUNNING",
            autonomy: "agentic",
            created_at: "2026-08-10T00:00:00Z",
            task_count: 3,
          },
        ]),
      ),
    );

    const runs = await api.runs();
    expect(runs[0].goalId).toBe("P01-G01");
    expect(runs[0].taskCount).toBe(3);
  });

  it("leaves event payload keys untouched", async () => {
    // Payloads round-trip to the backend; renaming their keys would corrupt
    // values that are opaque to the client.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        mockResponse([
          {
            id: "evt-1",
            timestamp: "2026-08-10T00:00:00Z",
            type: "atlas.task.ready",
            run_id: "run-1",
            payload: { task_id: "task-1", previous: "PLANNED" },
          },
        ]),
      ),
    );

    const events = await api.run("run-1") as unknown as Array<{
      runId: string;
      payload: Record<string, unknown>;
    }>;
    expect(events[0].runId).toBe("run-1");
    expect(events[0].payload).toEqual({ task_id: "task-1", previous: "PLANNED" });
  });

  it("preserves gate names, which are not snake_case fields", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        mockResponse({
          id: "P01-G01",
          gates: { build: "required", documentation: "required" },
        }),
      ),
    );

    const goal = await api.goal("P01-G01");
    expect(goal.gates).toEqual({ build: "required", documentation: "required" });
  });

  it("reads the routing view, including nested role and stat fields", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        mockResponse({
          state: "degraded",
          reachable: false,
          degraded: true,
          reason: "Command Code (cmd) is not on PATH",
          probed_at: "2026-08-10T00:00:00Z",
          available: [],
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
              uses: 4,
              successes: 3,
              failures: 1,
              success_rate: 0.75,
              average_latency_ms: 120.5,
            },
          ],
        }),
      ),
    );

    const routing = await api.routing();
    expect(routing.state).toBe("degraded");
    expect(routing.probedAt).toBe("2026-08-10T00:00:00Z");
    expect(routing.roles[0].fallbackAttempts).toBe(0);
    expect(routing.stats[0].modelKey).toBe("deepseek-v4-pro");
    expect(routing.stats[0].averageLatencyMs).toBe(120.5);
  });

  it("raises ApiError carrying the backend detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => mockResponse({ detail: "Unknown Goal: P99-G01" }, false, 404)),
    );

    await expect(api.goal("P99-G01")).rejects.toThrowError(ApiError);
    await expect(api.goal("P99-G01")).rejects.toThrow("Unknown Goal: P99-G01");
  });

  it("falls back to the status text when the body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => {
          throw new Error("not json");
        },
      }) as unknown as Response),
    );

    await expect(api.goals()).rejects.toThrow("Internal Server Error");
  });
});

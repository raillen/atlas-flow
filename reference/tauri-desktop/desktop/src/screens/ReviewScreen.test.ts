import { describe, expect, it } from "vitest";
import type { RoutingView } from "../api";
import { describeRegistry } from "./ReviewScreen";

function routing(overrides: Partial<RoutingView>): RoutingView {
  return {
    state: "pending",
    reachable: false,
    degraded: false,
    reason: "",
    probedAt: "",
    available: [],
    roles: [],
    stats: [],
    ...overrides,
  };
}

describe("describeRegistry", () => {
  it("says the probe is still running rather than reporting a failure", () => {
    expect(describeRegistry(routing({ state: "pending" }))).toContain("Asking");
  });

  it("explains a degraded registry with the reason it gave", () => {
    const text = describeRegistry(
      routing({
        state: "degraded",
        degraded: true,
        reason: "Command Code (cmd) is not on PATH",
      }),
    );
    expect(text).toContain("policy roster");
    expect(text).toContain("not on PATH");
  });

  it("counts the models a reachable registry reported", () => {
    const text = describeRegistry(
      routing({
        state: "reachable",
        reachable: true,
        available: ["deepseek/deepseek-v4-pro", "gpt-5.6-luna"],
      }),
    );
    expect(text).toBe("2 model(s) reachable.");
  });
});

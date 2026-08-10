import { describe, expect, it } from "vitest";

import type { Goal, GoalState } from "./index";

describe("domain types", () => {
  it("accepts the Goal states used by Project Atlas goal files", () => {
    const states: GoalState[] = ["PLANNED", "READY", "ACTIVE", "BLOCKED", "DONE", "CANCELLED"];
    expect(states).toContain("PLANNED");
  });

  it("models a Goal with locked acceptance criteria and gates", () => {
    const goal: Goal = {
      id: "P00-G01",
      phase: "P00",
      title: "Repository Foundation",
      state: "PLANNED",
      objective: "foundation",
      constraints: [],
      acceptance: ["Repository builds from clean checkout"],
      dependencies: [],
      gates: { build: "required", tests: "required", review: "required", documentation: "required" },
    };
    expect(goal.acceptance).toHaveLength(1);
  });
});

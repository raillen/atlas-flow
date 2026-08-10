import { describe, expect, it } from "vitest";

import { createDomainEvent, isAtlasEventType } from "./index";

describe("ag-ui client", () => {
  it("accepts namespaced Atlas event types", () => {
    expect(isAtlasEventType("atlas.goal.loaded")).toBe(true);
    expect(isAtlasEventType("atlas.evidence.attached")).toBe(true);
    expect(isAtlasEventType("raw.provider.stream")).toBe(false);
  });

  it("creates envelope with id, timestamp, project, type and version", () => {
    const event = createDomainEvent("atlas.goal.loaded", "atlas-flow", { goalId: "P00-G01" }, "run-1");
    expect(event.id).toBeTruthy();
    expect(event.version).toBe(1);
    expect(event.runId).toBe("run-1");
    expect(event.payload).toEqual({ goalId: "P00-G01" });
  });

  it("rejects non-namespaced event types", () => {
    expect(() => createDomainEvent("goal.loaded", "atlas-flow", {})).toThrow();
  });
});

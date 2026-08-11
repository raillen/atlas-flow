import { describe, expect, it } from "vitest";
import {
  STAGES,
  STAGE_LABELS,
  STAGE_PURPOSE,
  nextStageIndex,
} from "./Workspace";

describe("stage navigation", () => {
  it("wraps around with the arrow keys", () => {
    expect(nextStageIndex("ArrowRight", STAGES.length - 1, STAGES.length)).toBe(0);
    expect(nextStageIndex("ArrowLeft", 0, STAGES.length)).toBe(STAGES.length - 1);
  });

  it("moves one step at a time", () => {
    expect(nextStageIndex("ArrowRight", 0, STAGES.length)).toBe(1);
    expect(nextStageIndex("ArrowLeft", 2, STAGES.length)).toBe(1);
  });

  it("jumps to the ends with Home and End", () => {
    expect(nextStageIndex("Home", 3, STAGES.length)).toBe(0);
    expect(nextStageIndex("End", 0, STAGES.length)).toBe(STAGES.length - 1);
  });

  it("ignores keys that are not navigation", () => {
    expect(nextStageIndex("a", 1, STAGES.length)).toBeNull();
    expect(nextStageIndex("Enter", 1, STAGES.length)).toBeNull();
  });
});

describe("stages", () => {
  it("runs in pipeline order", () => {
    // Five equal tabs said nothing about sequence, which is why nobody could
    // tell what to do next. The order is the message.
    expect(STAGES).toEqual(["discuss", "plan", "build", "review", "docs"]);
  });

  it("every stage says what it answers", () => {
    // A label alone leaves the reader guessing what a stage is for.
    for (const stage of STAGES) {
      expect(STAGE_LABELS[stage], stage).toBeTruthy();
      expect(STAGE_PURPOSE[stage], stage).toBeTruthy();
      expect(STAGE_PURPOSE[stage].length, stage).toBeGreaterThan(10);
    }
  });
});

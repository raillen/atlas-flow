import { describe, expect, it } from "vitest";
import { TABS, nextTabIndex } from "./App";

describe("tab keyboard navigation", () => {
  it("wraps around with the arrow keys", () => {
    expect(nextTabIndex("ArrowRight", TABS.length - 1, TABS.length)).toBe(0);
    expect(nextTabIndex("ArrowLeft", 0, TABS.length)).toBe(TABS.length - 1);
  });

  it("moves one step at a time", () => {
    expect(nextTabIndex("ArrowRight", 0, TABS.length)).toBe(1);
    expect(nextTabIndex("ArrowLeft", 2, TABS.length)).toBe(1);
  });

  it("jumps to the ends with Home and End", () => {
    expect(nextTabIndex("Home", 3, TABS.length)).toBe(0);
    expect(nextTabIndex("End", 0, TABS.length)).toBe(TABS.length - 1);
  });

  it("ignores keys that are not navigation", () => {
    expect(nextTabIndex("a", 1, TABS.length)).toBeNull();
    expect(nextTabIndex("Enter", 1, TABS.length)).toBeNull();
  });
});

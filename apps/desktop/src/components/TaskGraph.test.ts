import { describe, expect, it } from "vitest";
import type { TaskView } from "../api";
import {
  NODE_WIDTH,
  describeGraph,
  edgesFor,
  graphSize,
  placeTasks,
} from "./TaskGraph";

function task(id: string, dependencies: string[] = []): TaskView {
  return {
    id,
    objective: `Do ${id}`,
    state: "PLANNED",
    role: null,
    risk: "medium",
    scope: [],
    dependencies,
  };
}

describe("placeTasks", () => {
  it("gives each dependency layer its own column", () => {
    const placed = placeTasks([[task("a"), task("b")], [task("c", ["a"])]]);

    const columns = new Set(placed.map((item) => item.x));
    expect(columns.size).toBe(2);
    expect(placed.find((item) => item.task.id === "c")!.x).toBeGreaterThan(
      placed.find((item) => item.task.id === "a")!.x,
    );
  });

  it("stacks tasks within a layer without overlapping them", () => {
    const placed = placeTasks([[task("a"), task("b")]]);

    expect(placed[0].x).toBe(placed[1].x);
    expect(placed[0].y).not.toBe(placed[1].y);
  });

  it("places nothing for an empty plan", () => {
    expect(placeTasks([])).toEqual([]);
    expect(graphSize([])).toEqual({ width: 0, height: 0 });
  });
});

describe("edgesFor", () => {
  it("draws an edge for every dependency between placed tasks", () => {
    const placed = placeTasks([[task("a")], [task("b", ["a"])]]);

    expect(edgesFor(placed)).toEqual([{ from: "a", to: "b" }]);
  });

  it("ignores a dependency on a task that is not shown", () => {
    // A dangling edge would point at nothing and read as a rendering fault.
    const placed = placeTasks([[task("b", ["missing"])]]);

    expect(edgesFor(placed)).toEqual([]);
  });

  it("draws every edge of a task that waits for several", () => {
    const placed = placeTasks([
      [task("a"), task("b")],
      [task("c", ["a", "b"])],
    ]);

    expect(edgesFor(placed)).toHaveLength(2);
  });
});

describe("graphSize", () => {
  it("is wide enough for the last column", () => {
    const placed = placeTasks([[task("a")], [task("b", ["a"])]]);
    const last = Math.max(...placed.map((item) => item.x));

    expect(graphSize(placed).width).toBe(last + NODE_WIDTH);
  });
});

describe("describeGraph", () => {
  it("says the same thing the picture does", () => {
    // The list beside the graph is a peer, not a fallback: a drawing alone is
    // unreadable to a screen reader.
    const text = describeGraph([[task("a"), task("b")], [task("c", ["a"])]]);

    expect(text).toContain("3 task(s) in 2 stage(s)");
    expect(text).toContain("stage 1: 2");
    expect(text).toContain("stage 2: 1");
  });

  it("says a plan is empty rather than describing nothing", () => {
    expect(describeGraph([])).toBe("This plan has no tasks.");
  });
});

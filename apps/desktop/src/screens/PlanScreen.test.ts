import { describe, expect, it } from "vitest";
import { layerTasks } from "./PlanScreen";
import type { TaskView } from "../api";

function task(id: string, dependencies: string[] = []): TaskView {
  return {
    id,
    objective: id,
    state: "PLANNED",
    role: null,
    risk: "medium",
    scope: [],
    dependencies,
  };
}

describe("layerTasks", () => {
  it("puts independent tasks in the first layer", () => {
    const layers = layerTasks([task("a"), task("b")]);
    expect(layers).toHaveLength(1);
    expect(layers[0].map((t) => t.id)).toEqual(["a", "b"]);
  });

  it("places a task after everything it depends on", () => {
    const layers = layerTasks([
      task("c", ["a", "b"]),
      task("a"),
      task("b", ["a"]),
    ]);

    expect(layers.map((layer) => layer.map((t) => t.id))).toEqual([
      ["a"],
      ["b"],
      ["c"],
    ]);
  });

  it("ignores dependencies on tasks that are not in the plan", () => {
    const layers = layerTasks([task("a", ["ghost"])]);
    expect(layers[0].map((t) => t.id)).toEqual(["a"]);
  });

  it("does not hang on a dependency cycle", () => {
    // The backend rejects cyclic plans, but the view must not lock up if one
    // ever reaches it.
    const layers = layerTasks([task("a", ["b"]), task("b", ["a"])]);
    expect(layers.flat()).toHaveLength(2);
  });
});

import { describe, expect, it } from "vitest";
import type { AgUiMessage } from "@atlas-flow/ag-ui-client";
import { toActivity } from "./useAgentStream";

function message(type: string, payload: Record<string, unknown>): AgUiMessage {
  return { type, timestamp: "2026-08-10T00:00:00Z", payload };
}

describe("toActivity", () => {
  it("reads terminal output with the command that produced it", () => {
    const entry = toActivity(
      message("atlas.terminal.output", {
        task_id: "task-1",
        text: "2 passed\n",
        tool: "pytest -q",
        status: "completed",
        paths: [],
      }),
      0,
    );

    expect(entry).not.toBeNull();
    expect(entry?.taskId).toBe("task-1");
    expect(entry?.tool).toBe("pytest -q");
    expect(entry?.text).toBe("2 passed\n");
  });

  it("reads the paths of a file change", () => {
    const entry = toActivity(
      message("atlas.file.changed", { paths: ["a.py", "b.py"] }),
      1,
    );

    expect(entry?.paths).toEqual(["a.py", "b.py"]);
  });

  it("ignores run events, which the durable event log already shows", () => {
    expect(toActivity(message("atlas.task.ready", { task_id: "t" }), 0)).toBeNull();
  });

  it("survives a payload missing every optional field", () => {
    const entry = toActivity(message("atlas.agent.message", {}), 0);

    expect(entry).not.toBeNull();
    expect(entry?.text).toBe("");
    expect(entry?.paths).toEqual([]);
  });

  it("gives each entry a distinct key even at the same timestamp", () => {
    const first = toActivity(message("atlas.agent.message", { text: "a" }), 0);
    const second = toActivity(message("atlas.agent.message", { text: "b" }), 1);

    expect(first?.key).not.toBe(second?.key);
  });
});

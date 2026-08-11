import { afterEach, describe, expect, it, vi } from "vitest";
import { desktop, isDesktop, projectName } from "./desktop";
import { describeEngine } from "./workspace/EngineStatus";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubBridge(result: unknown) {
  const invoke = vi.fn(async () => result);
  vi.stubGlobal("__TAURI__", { core: { invoke } });
  return invoke;
}

describe("desktop bridge", () => {
  it("reports no shell when running in a plain browser", () => {
    expect(isDesktop()).toBe(false);
  });

  it("resolves to null outside the shell instead of throwing", async () => {
    // Every screen has to work under `vite dev`, where there is no Tauri.
    await expect(desktop.backendStatus()).resolves.toBeNull();
    await expect(desktop.projectRoot()).resolves.toBeNull();
  });

  it("converts the Rust snake_case status to the UI's naming", async () => {
    const invoke = stubBridge({
      running: true,
      url: "http://localhost:8000",
      command: ["uv", "run"],
      project_root: "/srv/atlas",
      log_path: "/tmp/atlas-flow-backend.log",
    });

    const status = await desktop.backendStatus();

    expect(invoke).toHaveBeenCalledWith("backend_status");
    expect(status).toEqual({
      running: true,
      url: "http://localhost:8000",
      command: ["uv", "run"],
      projectRoot: "/srv/atlas",
      logPath: "/tmp/atlas-flow-backend.log",
    });
  });

  it("detects the shell once the bridge is present", () => {
    stubBridge(null);
    expect(isDesktop()).toBe(true);
  });
});

describe("describeEngine", () => {
  it("says there is nothing to manage in a browser", () => {
    expect(describeEngine(null)).toContain("Browser");
  });

  it("names the address when the engine is up", () => {
    expect(
      describeEngine({
        running: true,
        url: "http://127.0.0.1:8123",
        command: [],
        projectRoot: "/srv/atlas",
        logPath: "/tmp/atlas-flow-backend.log",
      }),
    ).toBe("Engine at http://127.0.0.1:8123");
  });

  it("says so plainly when it is stopped", () => {
    expect(
      describeEngine({
        running: false,
        url: "http://127.0.0.1:8123",
        command: ["uv", "run", "uvicorn"],
        projectRoot: "/srv/atlas",
        logPath: "/tmp/atlas-flow-backend.log",
      }),
    ).toBe("Engine stopped");
  });
});

describe("projectName", () => {
  it("uses the last segment, which is what people call a project", () => {
    expect(projectName("/home/someone/code/atlas-flow")).toBe("atlas-flow");
  });

  it("survives a trailing slash", () => {
    expect(projectName("/srv/atlas/")).toBe("atlas");
  });

  it("returns the path itself when there is no segment to take", () => {
    expect(projectName("/")).toBe("/");
    expect(projectName("")).toBe("");
  });
});

describe("openProject", () => {
  it("passes the path the shell needs", async () => {
    const invoke = stubBridge({
      running: true,
      url: "http://localhost:8000",
      command: [],
      project_root: "/srv/other",
      log_path: "/tmp/log",
    });

    const status = await desktop.openProject("/srv/other");

    expect(invoke).toHaveBeenCalledWith("open_project", { path: "/srv/other" });
    expect(status?.projectRoot).toBe("/srv/other");
  });

  it("reports no recents outside the shell rather than throwing", async () => {
    await expect(desktop.recentProjects()).resolves.toEqual([]);
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { desktop, isDesktop } from "./desktop";
import { describeBackend } from "./screens/ProjectScreen";

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
    });

    const status = await desktop.backendStatus();

    expect(invoke).toHaveBeenCalledWith("backend_status");
    expect(status).toEqual({
      running: true,
      url: "http://localhost:8000",
      command: ["uv", "run"],
      projectRoot: "/srv/atlas",
    });
  });

  it("detects the shell once the bridge is present", () => {
    stubBridge(null);
    expect(isDesktop()).toBe(true);
  });
});

describe("describeBackend", () => {
  it("says the shell manages nothing in a browser", () => {
    expect(describeBackend(null)).toContain("browser");
  });

  it("names the command it would run when nothing is started", () => {
    const text = describeBackend({
      running: false,
      url: "http://localhost:8000",
      command: ["uv", "run", "uvicorn"],
      projectRoot: "/srv/atlas",
    });

    expect(text).toContain("uv run uvicorn");
  });

  it("names the url when the backend is up", () => {
    const text = describeBackend({
      running: true,
      url: "http://localhost:8000",
      command: [],
      projectRoot: "/srv/atlas",
    });

    expect(text).toBe("Backend running at http://localhost:8000");
  });
});

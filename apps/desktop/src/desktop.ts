/**
 * Bridge to the Tauri shell (apps/desktop/src-tauri/src/lib.rs).
 *
 * Every screen must also work in a plain browser during development, so this
 * module never assumes the shell is there: outside Tauri `isDesktop` is false
 * and each call resolves to null rather than throwing.
 */

export interface BackendStatus {
  running: boolean;
  url: string;
  command: string[];
  projectRoot: string;
  /** Where a backend this shell started writes its output. */
  logPath: string;
}

interface TauriBridge {
  core: {
    invoke: <T>(command: string, args?: Record<string, unknown>) => Promise<T>;
  };
}

function bridge(): TauriBridge | null {
  const global = globalThis as { __TAURI__?: TauriBridge };
  return global.__TAURI__ ?? null;
}

export const isDesktop = (): boolean => bridge() !== null;

async function call<T>(command: string): Promise<T | null> {
  const tauri = bridge();
  if (tauri === null) return null;
  return await tauri.core.invoke<T>(command);
}

/** The Rust side serializes snake_case; keep the UI's naming intact. */
interface RawStatus {
  running: boolean;
  url: string;
  command: string[];
  project_root: string;
  log_path: string;
}

function toStatus(raw: RawStatus | null): BackendStatus | null {
  if (raw === null) return null;
  return {
    running: raw.running,
    url: raw.url,
    command: raw.command,
    projectRoot: raw.project_root,
    logPath: raw.log_path,
  };
}

/** The last path segment, which is what a person calls the project. */
export function projectName(path: string): string {
  const parts = path.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

async function callWith<T>(
  command: string,
  args: Record<string, unknown>,
): Promise<T | null> {
  const tauri = bridge();
  if (tauri === null) return null;
  return await tauri.core.invoke<T>(command, args);
}

/**
 * Ask the shell for a folder.
 *
 * Returns null both when there is no shell and when the person cancelled the
 * dialog — the caller does nothing in either case, and distinguishing them
 * would only invite an error message for a deliberate choice.
 */
async function pickFolder(): Promise<string | null> {
  const tauri = bridge();
  if (tauri === null) return null;
  const chosen = await tauri.core.invoke<string | string[] | null>(
    "plugin:dialog|open",
    { options: { directory: true, multiple: false, title: "Open a project" } },
  );
  if (chosen === null || chosen === undefined) return null;
  return Array.isArray(chosen) ? (chosen[0] ?? null) : chosen;
}

export const desktop = {
  backendStatus: async () => toStatus(await call<RawStatus>("backend_status")),
  startBackend: async () => toStatus(await call<RawStatus>("start_backend")),
  stopBackend: async () => toStatus(await call<RawStatus>("stop_backend")),
  projectRoot: () => call<string>("project_root"),
  recentProjects: async () => (await call<string[]>("recent_projects")) ?? [],
  openProject: async (path: string) =>
    toStatus(await callWith<RawStatus>("open_project", { path })),
  pickFolder,
};

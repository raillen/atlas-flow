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
}

function toStatus(raw: RawStatus | null): BackendStatus | null {
  if (raw === null) return null;
  return {
    running: raw.running,
    url: raw.url,
    command: raw.command,
    projectRoot: raw.project_root,
  };
}

export const desktop = {
  backendStatus: async () => toStatus(await call<RawStatus>("backend_status")),
  startBackend: async () => toStatus(await call<RawStatus>("start_backend")),
  stopBackend: async () => toStatus(await call<RawStatus>("stop_backend")),
  projectRoot: () => call<string>("project_root"),
};

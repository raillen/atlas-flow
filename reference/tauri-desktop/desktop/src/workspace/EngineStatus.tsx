import type { FC } from "react";
import { useCallback, useEffect, useState } from "react";
import { desktop, type BackendStatus } from "../desktop";
import { space, surface, text, tone, type } from "../theme";

/** The one line the status bar shows about the engine. */
export function describeEngine(status: BackendStatus | null): string {
  if (status === null) return "Browser — no engine to manage";
  if (status.running) return `Engine at ${status.url}`;
  return "Engine stopped";
}

/**
 * Whether the engine is running, in the status bar.
 *
 * It used to live inside a panel two tabs away, which meant the single fact
 * that decides whether anything in the window can work at all was the one fact
 * you had to go looking for. Every empty list and failed request in this app
 * has the same first question behind it, and this answers it without being
 * asked.
 */
export const EngineStatus: FC<{ epoch: number; onChanged: () => void }> = ({
  epoch,
  onChanged,
}) => {
  const [status, setStatus] = useState<BackendStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Opening a project starts its engine.
  //
  // The old shell opened onto empty lists and failing requests until you found
  // a Start button in a tab, which made a working app look broken on first
  // launch. Starting is what the window was opened to do; the control below
  // stays for stopping it, and for saying so when starting fails.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const current = await desktop.backendStatus();
      if (cancelled || current === null) {
        setStatus(current);
        return;
      }
      if (current.running) {
        setStatus(current);
        return;
      }
      setBusy(true);
      try {
        const started = await desktop.startBackend();
        if (!cancelled) {
          setStatus(started);
          setError(null);
          onChanged();
        }
      } catch (cause: unknown) {
        if (!cancelled) {
          setStatus(current);
          setError(cause instanceof Error ? cause.message : String(cause));
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // onChanged is stable per project; re-running on it would restart the
    // engine every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [epoch]);

  const act = useCallback(
    async (action: () => Promise<BackendStatus | null>) => {
      setBusy(true);
      try {
        setStatus(await action());
        setError(null);
        onChanged();
      } catch (cause: unknown) {
        setError(cause instanceof Error ? cause.message : String(cause));
      } finally {
        setBusy(false);
      }
    },
    [onChanged],
  );

  // In a browser there is no shell to ask, and nothing to start.
  if (status === null) return null;

  const running = status.running;

  return (
    <span style={{ display: "flex", alignItems: "center", gap: space.snug }}>
      <span
        aria-hidden="true"
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: running ? tone.positive.fg : tone.negative.fg,
        }}
      />
      <span style={{ color: error ? text.danger : text.muted }} role={error ? "alert" : undefined}>
        {error ?? describeEngine(status)}
      </span>
      <button
        type="button"
        disabled={busy}
        onClick={() => void act(running ? desktop.stopBackend : desktop.startBackend)}
        style={{
          padding: `${space.hair}px ${space.snug}px`,
          border: `1px solid ${surface.border}`,
          borderRadius: 5,
          background: surface.card,
          color: text.primary,
          font: "inherit",
          fontSize: type.small,
          cursor: busy ? "wait" : "pointer",
        }}
      >
        {running ? "Stop engine" : "Start engine"}
      </button>
    </span>
  );
};

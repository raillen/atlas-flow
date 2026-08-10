import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/**
 * Runs an async loader and keeps its result, error and loading flag.
 *
 * Results from a superseded call are dropped: without that, a slow first
 * request can land after a faster second one and overwrite fresher data.
 */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);
  const generation = useRef(0);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    const current = ++generation.current;
    setLoading(true);

    loader()
      .then((result) => {
        if (current !== generation.current) return;
        setData(result);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (current !== generation.current) return;
        setError(cause instanceof Error ? cause.message : String(cause));
      })
      .finally(() => {
        if (current === generation.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return { data, error, loading, reload };
}

/** Re-runs `reload` on an interval while `active` is true. */
export function usePolling(reload: () => void, active: boolean, intervalMs = 1000): void {
  useEffect(() => {
    if (!active) return;
    const handle = window.setInterval(reload, intervalMs);
    return () => window.clearInterval(handle);
  }, [reload, active, intervalMs]);
}

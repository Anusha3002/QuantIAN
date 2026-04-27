import { useCallback, useEffect, useRef, useState } from "react";

interface PollingState<T> {
  data: T | null;
  error: string | null;
  lastUpdated: Date | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled = true,
): PollingState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const mountedRef = useRef(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const run = useCallback(async () => {
    try {
      setLoading((prev) => (data === null ? true : prev));
      const result = await fetcherRef.current();
      if (!mountedRef.current) return;
      setData(result);
      setError(null);
      setLastUpdated(new Date());
    } catch (exc) {
      if (!mountedRef.current) return;
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [data]);

  useEffect(() => {
    mountedRef.current = true;
    if (!enabled) return;
    run();
    const id = window.setInterval(run, intervalMs);
    return () => {
      mountedRef.current = false;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, enabled]);

  return { data, error, lastUpdated, loading, refresh: run };
}

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

export function usePublishedSurvey({ enabled = true } = {}) {
  const [options, setOptions] = useState(null);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    const opts = await api("/api/auth/options");
    setOptions(opts);
    setError("");
    return opts;
  }, []);

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    reload().catch((err) => {
      if (!cancelled) setError(err.message || "Unable to load the Graduate Tracer Survey.");
    });
    return () => {
      cancelled = true;
    };
  }, [enabled, reload]);

  return { options, error, reload, schema: options?.survey };
}

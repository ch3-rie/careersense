import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

export const SURVEY_REVISION_KEY = "cs_survey_revision";
const SURVEY_EVENT = "careersense:survey-updated";
const CHANNEL_NAME = "careersense-survey";

function writeRevision(version) {
  const value = String(version ?? Date.now());
  try {
    localStorage.setItem(SURVEY_REVISION_KEY, value);
  } catch {
    /* ignore quota / private mode */
  }
  return value;
}

export function notifyPublishedSurvey(version) {
  const value = writeRevision(version);
  window.dispatchEvent(new CustomEvent(SURVEY_EVENT, { detail: { version: value } }));
  try {
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channel.postMessage({ version: value });
    channel.close();
  } catch {
    /* BroadcastChannel is optional */
  }
}

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
    let channel;

    reload().catch((err) => {
      if (!cancelled) setError(err.message || "Unable to load the Graduate Tracer Survey.");
    });

    function refresh() {
      reload().catch(() => {});
    }

    function onStorage(event) {
      if (event.key === SURVEY_REVISION_KEY) refresh();
    }

    function onVisibility() {
      if (!document.hidden) refresh();
    }

    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("storage", onStorage);
    window.addEventListener(SURVEY_EVENT, refresh);
    try {
      channel = new BroadcastChannel(CHANNEL_NAME);
      channel.onmessage = refresh;
    } catch {
      channel = null;
    }
    const timer = window.setInterval(refresh, 20000);

    return () => {
      cancelled = true;
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(SURVEY_EVENT, refresh);
      channel?.close();
      window.clearInterval(timer);
    };
  }, [enabled, reload]);

  return { options, error, reload, schema: options?.survey };
}

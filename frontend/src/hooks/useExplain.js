import { useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const RETRY_DELAY_MS = 3000;

/** Loads the backend's real formula constants (/api/explain) once, retrying
 * until the backend is up. Explanations on screen quote these values rather
 * than hand-copied numbers, so they can't drift from what's computed. */
export function useExplain() {
  const [explain, setExplain] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let timer;

    async function load() {
      try {
        const res = await fetch(`${API_BASE_URL}/api/explain`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) setExplain(data);
      } catch {
        if (!cancelled) timer = setTimeout(load, RETRY_DELAY_MS);
      }
    }

    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  return explain;
}

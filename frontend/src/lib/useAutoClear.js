import { useEffect } from "react";

export function useAutoClear(value, clear, ms = 4500) {
  useEffect(() => {
    if (!value) return undefined;
    const timer = window.setTimeout(() => clear(""), ms);
    return () => window.clearTimeout(timer);
  }, [value, clear, ms]);
}

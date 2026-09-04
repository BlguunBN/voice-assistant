import { useEffect, useState } from "react";
import { getDesktopStatus } from "../api/client";
import type { DesktopStatus } from "../types";

export function useDesktopStatus() {
  const [status, setStatus] = useState<DesktopStatus>({
    status: "offline",
    transcript: null,
    detail: null,
    updated_at: 0,
    selected_language: "auto",
    detected_language: null,
  });
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const nextStatus = await getDesktopStatus();
        if (!active) return;
        setStatus(nextStatus);
        setError(null);
      } catch (requestError) {
        if (!active) return;
        setError(requestError instanceof Error ? requestError.message : "Overlay status unavailable");
      } finally {
        if (active) setNow(Date.now());
      }
    };

    void poll();
    const timer = window.setInterval(() => void poll(), 300);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  return { status, error, now };
}

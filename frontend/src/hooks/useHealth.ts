import { useEffect, useState } from "react";
import { getHealth } from "../api/client";
import type { Health } from "../types";

export function useHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const nextHealth = await getHealth();
        if (!active) return;
        setHealth(nextHealth);
        setError(null);
      } catch (requestError) {
        if (!active) return;
        setError(requestError instanceof Error ? requestError.message : "API connection failed");
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 5_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  return { health, error };
}

import { useEffect, useState } from "react";

import { fetchHealth } from "../api/pipeline";

const POLL_MS = 30000;

// status: "checking" | "online" | "warming" | "degraded" | "offline"
export function useHealth() {
  const [health, setHealth] = useState({ status: "checking", models: [] });

  useEffect(() => {
    const controller = new AbortController();

    const check = async () => {
      try {
        const data = await fetchHealth(controller.signal);
        const models = data.ollama_models || [];
        const notReady = models.filter((model) => !model.ok);
        let status = "online";
        if (notReady.length > 0) {
          status = notReady.every((model) => /pending/i.test(model.message || "")) ? "warming" : "degraded";
        }
        setHealth({ status, models });
      } catch (error) {
        if (error.name !== "AbortError") {
          setHealth({ status: "offline", models: [] });
        }
      }
    };

    check();
    const timer = window.setInterval(check, POLL_MS);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, []);

  return health;
}

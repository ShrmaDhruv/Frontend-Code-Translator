import { useCallback, useState } from "react";

import { runPipeline } from "../api/pipeline";
import { API_BASE } from "../constants";

const IDLE = { status: "idle", result: null, errors: [], warnings: [], startedAt: 0, elapsedMs: 0 };

// status: "idle" | "running" | "done" | "failed"
export function usePipeline() {
  const [run, setRun] = useState(IDLE);

  const reset = useCallback(() => setRun(IDLE), []);

  const fail = useCallback((messages) => {
    setRun({ ...IDLE, status: "failed", errors: messages });
  }, []);

  const start = useCallback(async (payload) => {
    const startedAt = Date.now();
    setRun({ ...IDLE, status: "running", startedAt });

    try {
      const data = await runPipeline(payload);
      setRun({
        status: data.ok ? "done" : "failed",
        result: data,
        errors: data.errors || [],
        warnings: data.warnings || [],
        startedAt,
        elapsedMs: Date.now() - startedAt,
      });
      return data;
    } catch (error) {
      const messages = [error.message];
      if (error instanceof TypeError) {
        messages.push(`Could not reach the API at ${API_BASE || window.location.origin}. Is the backend running?`);
      }
      setRun({ ...IDLE, status: "failed", errors: messages, startedAt, elapsedMs: Date.now() - startedAt });
      return null;
    }
  }, []);

  return { run, start, fail, reset };
}

import { useEffect, useState } from "react";

import { PIPELINE_STEPS } from "../constants";
import { CheckIcon, CrossIcon } from "./Icons";

const STEP_INDEX = Object.fromEntries(PIPELINE_STEPS.map((step, index) => [step.id, index]));

// Maps a pipeline response to one state per step: idle | done | failed | attention | skipped.
function stepStates(run) {
  const states = PIPELINE_STEPS.map(() => "idle");
  const { result } = run;
  if (!result) return states;

  const mark = (upTo, state) => {
    for (let index = 0; index <= STEP_INDEX[upTo]; index += 1) states[index] = state;
  };

  if (result.stage === "input") {
    states[STEP_INDEX.guard] = "failed";
  } else if (result.stage === "detect") {
    mark("detect", "done");
    if (!result.ok) states[STEP_INDEX.detect] = "attention";
  } else if (result.stage === "ir") {
    mark("ir", "done");
  } else if (result.stage === "translate") {
    mark("validate", "done");
    if (result.source === result.target) {
      // Same framework: the code is returned unchanged, nothing is generated.
      states[STEP_INDEX.translate] = "skipped";
      states[STEP_INDEX.validate] = "skipped";
    } else if (!result.ok) {
      states[STEP_INDEX.validate] = "failed";
    }
  }
  return states;
}

function formatSeconds(ms) {
  return `${(ms / 1000).toFixed(1)}s`;
}

function useElapsed(run) {
  const [now, setNow] = useState(() => Date.now());
  const isRunning = run.status === "running";

  useEffect(() => {
    if (!isRunning) return undefined;
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, [isRunning]);

  return isRunning ? Math.max(0, now - run.startedAt) : run.elapsedMs;
}

function summary(run, states, elapsed) {
  if (run.status === "running") return `Running · ${formatSeconds(elapsed)}`;
  if (run.status === "idle") return "Ready";

  const stoppedAt = states.findIndex((state) => state === "failed" || state === "attention");
  if (stoppedAt >= 0) {
    const verb = states[stoppedAt] === "attention" ? "Needs input at" : "Stopped at";
    return `${verb} ${PIPELINE_STEPS[stoppedAt].label} · ${formatSeconds(elapsed)}`;
  }
  if (run.status === "failed") return "Request failed";
  return `Completed in ${formatSeconds(elapsed)}`;
}

export function PipelineRail({ run }) {
  const elapsed = useElapsed(run);
  const states = stepStates(run);
  const isRunning = run.status === "running";

  return (
    <section className={`rail ${isRunning ? "is-running" : ""}`} aria-label="Pipeline progress">
      <ol className="rail-steps">
        {PIPELINE_STEPS.map((step, index) => (
          <li key={step.id} className={`rail-step step-${states[index]}`} style={{ "--i": index }}>
            <span className="rail-node">
              {states[index] === "done" && <CheckIcon size={11} />}
              {states[index] === "failed" && <CrossIcon size={11} />}
              {states[index] === "attention" && "?"}
            </span>
            <span className="rail-label">{step.label}</span>
            {states[index] === "skipped" && <span className="rail-note">skipped</span>}
          </li>
        ))}
      </ol>
      <p
        className={`rail-summary summary-${states.includes("attention") ? "attention" : run.status}`}
        aria-live="polite"
      >
        {summary(run, states, elapsed)}
      </p>
    </section>
  );
}

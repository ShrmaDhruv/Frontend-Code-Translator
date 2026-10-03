import { FRAMEWORK_META, TARGET_OPTIONS } from "../constants";
import { FrameworkIcon } from "./Icons";

// Shown when detection confidence is too low: the user picks the source and the pipeline re-runs.
export function ConfirmSource({ detection, onPick }) {
  const scores = detection.confidence_scores || {};

  return (
    <div className="confirm">
      <h3>Which framework is this?</h3>
      <p>
        Detection wasn't confident enough to continue
        {detection.framework ? ` (best guess: ${detection.framework})` : ""}. Pick the source framework
        to run the translation.
      </p>
      <div className="confirm-options">
        {TARGET_OPTIONS.map((framework) => (
          <button
            key={framework}
            className={`confirm-option ${framework === detection.framework ? "is-guess" : ""}`}
            style={{ "--fw": FRAMEWORK_META[framework].color }}
            onClick={() => onPick(framework)}
          >
            <FrameworkIcon framework={framework} size={18} />
            <span>{framework}</span>
            {framework in scores && <small>{scores[framework]}%</small>}
          </button>
        ))}
      </div>
    </div>
  );
}

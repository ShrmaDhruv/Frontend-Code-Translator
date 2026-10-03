import { FRAMEWORK_META } from "../constants";
import { FrameworkIcon } from "./Icons";

const METHOD_LABELS = {
  manual: "Selected manually",
  layer1: "Rule-based detector",
  layer3: "LLM detector",
  input_guard: "Blocked by the input guard",
};

export function DetectionView({ detection }) {
  if (!detection) {
    return <p className="empty">Run a translation to see how the source framework was detected.</p>;
  }

  const scores = Object.entries(detection.confidence_scores || {}).sort((a, b) => b[1] - a[1]);
  const rawScores = detection.raw_scores || {};
  const meta = FRAMEWORK_META[detection.framework];

  return (
    <div className="detail">
      <div className="detail-hero" style={{ "--fw": meta?.color }}>
        {meta && <FrameworkIcon framework={detection.framework} size={26} />}
        <div>
          <strong>{detection.framework || "No framework"}</strong>
          <span>
            {detection.confidence} confidence · {METHOD_LABELS[detection.source] || detection.source}
          </span>
        </div>
      </div>

      {scores.length > 0 && (
        <section className="detail-section">
          <h3>Rule scores</h3>
          <ul className="bars">
            {scores.map(([framework, percent]) => (
              <li key={framework} style={{ "--fw": FRAMEWORK_META[framework]?.color }}>
                <span className="bar-name">{framework}</span>
                <span className="bar-track">
                  <span className="bar-fill" style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
                </span>
                <span className="bar-value">{percent}%</span>
                {framework in rawScores && <span className="bar-raw">{rawScores[framework]} pts</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {detection.reasoning && (
        <section className="detail-section">
          <h3>Reasoning</h3>
          <p className="detail-text">{detection.reasoning}</p>
        </section>
      )}
    </div>
  );
}

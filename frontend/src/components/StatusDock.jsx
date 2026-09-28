import { StatusPill } from "./StatusPill";

export function StatusDock({ confidence, warnings, errors }) {
  return (
    <footer className="status-dock">
      <StatusPill
        label="Confidence"
        value={confidence}
        color={confidence === "low" ? "#fbbf24" : "#42d392"}
      />
      <StatusPill label="Backend" value="127.0.0.1:8000" color="#a78bfa" />

      <div className="message-strip">
        {errors.length > 0 ? (
          errors.map((error) => (
            <span className="msg error" key={error}>
              {error}
            </span>
          ))
        ) : warnings.length > 0 ? (
          warnings.map((warning) => (
            <span className="msg warning" key={warning}>
              {warning}
            </span>
          ))
        ) : (
          <span className="msg muted">
            Ready. Paste code, choose a target, and run the pipeline.
          </span>
        )}
      </div>
    </footer>
  );
}

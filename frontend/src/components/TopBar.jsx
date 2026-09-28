import { StatusPill } from "./StatusPill";

export function TopBar({ detected, stage, sourceAccent }) {
  return (
    <header className="topbar">
      <div className="brand-block">
        <div className="brand-mark">FT</div>
        <div>
          <p className="eyebrow">AI assisted frontend migration</p>
          <h1>Frontend Code Translator</h1>
        </div>
      </div>

      <div className="top-actions">
        <StatusPill label="Detected" value={detected} color={sourceAccent} />
        <StatusPill
          label="Stage"
          value={stage}
          color={stage === "error" ? "#fb7185" : "#93c5fd"}
        />
      </div>
    </header>
  );
}

import { LogoMark, MoonIcon, SunIcon } from "./Icons";

const HEALTH_LABELS = {
  checking: "Checking API",
  online: "API online",
  warming: "Models loading",
  degraded: "Models unavailable",
  offline: "API offline",
};

export function Header({ health, theme, onToggleTheme }) {
  const modelSummary = health.models
    .map((model) => `${model.model}: ${model.ok ? "ready" : "not ready"}`)
    .join("\n");

  return (
    <header className="header">
      <div className="brand">
        <LogoMark />
        <div>
          <h1>Frontend Code Translator</h1>
          <p>Move components between React, Vue, Angular and HTML</p>
        </div>
      </div>

      <div className="header-actions">
        <div className={`health health-${health.status}`} title={modelSummary || undefined}>
          <span className="health-dot" />
          {HEALTH_LABELS[health.status]}
        </div>
        <button
          className="icon-btn"
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </button>
      </div>
    </header>
  );
}

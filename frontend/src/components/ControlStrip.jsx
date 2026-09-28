import { SelectControl } from "./SelectControl";

export function ControlStrip({
  sourceFramework,
  targetFramework,
  sourceAccent,
  targetAccent,
  sourceOptions,
  targetOptions,
  isRunning,
  onSourceChange,
  onTargetChange,
  onTranslate,
}) {
  return (
    <section className="control-strip">
      <SelectControl
        label="Source Framework"
        value={sourceFramework}
        options={sourceOptions}
        color={sourceAccent}
        onChange={onSourceChange}
      />

      <div className="flow-arrow">
        <span />
      </div>

      <SelectControl
        label="Target Framework"
        value={targetFramework}
        options={targetOptions}
        color={targetAccent}
        onChange={onTargetChange}
      />

      <button className="translate-btn" onClick={onTranslate} disabled={isRunning}>
        <span className={isRunning ? "spinner" : "btn-dot"} />
        {isRunning ? "Running Pipeline" : "Translate"}
      </button>
    </section>
  );
}

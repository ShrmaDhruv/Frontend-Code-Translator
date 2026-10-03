import { FRAMEWORK_META } from "../constants";
import { FrameworkIcon, PlayIcon, SwapIcon } from "./Icons";

function FrameworkPicker({ label, value, options, onChange, disabled }) {
  return (
    <div className="picker" role="group" aria-label={`${label} framework`}>
      <span className="picker-label">{label}</span>
      <div className="picker-options">
        {options.map((option) => (
          <button
            key={option}
            className="picker-option"
            style={{ "--fw": FRAMEWORK_META[option].color }}
            aria-pressed={option === value}
            disabled={disabled}
            onClick={() => onChange(option)}
          >
            <FrameworkIcon framework={option} />
            {FRAMEWORK_META[option].label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function RouteBar({
  source,
  target,
  sourceOptions,
  targetOptions,
  isRunning,
  canSwap,
  onSourceChange,
  onTargetChange,
  onSwap,
  onTranslate,
}) {
  return (
    <section className="route">
      <FrameworkPicker
        label="From"
        value={source}
        options={sourceOptions}
        onChange={onSourceChange}
        disabled={isRunning}
      />

      <button
        className="icon-btn swap-btn"
        onClick={onSwap}
        disabled={!canSwap || isRunning}
        aria-label="Swap source and target"
        title="Swap source and target"
      >
        <SwapIcon />
      </button>

      <FrameworkPicker
        label="To"
        value={target}
        options={targetOptions}
        onChange={onTargetChange}
        disabled={isRunning}
      />

      <button className="run-btn" onClick={onTranslate} disabled={isRunning}>
        {isRunning ? <span className="spinner" /> : <PlayIcon size={14} />}
        {isRunning ? "Translating" : "Translate"}
        {!isRunning && <kbd>Ctrl ↵</kbd>}
      </button>
    </section>
  );
}

import { AlertIcon, CrossIcon } from "./Icons";

export function Notices({ errors, warnings }) {
  if (errors.length === 0 && warnings.length === 0) {
    return (
      <footer className="notices">
        <p className="notice notice-hint">
          Paste a component, choose the target framework, then press <kbd>Ctrl ↵</kbd> to translate.
        </p>
      </footer>
    );
  }

  return (
    <footer className="notices" aria-live="polite">
      {errors.map((message) => (
        <p className="notice notice-error" key={`error-${message}`}>
          <CrossIcon size={14} />
          {message}
        </p>
      ))}
      {warnings.map((message) => (
        <p className="notice notice-warning" key={`warning-${message}`}>
          <AlertIcon size={14} />
          {message}
        </p>
      ))}
    </footer>
  );
}

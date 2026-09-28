export function EditorPanel({
  title,
  subtitle,
  color,
  value,
  onChange,
  readOnly = false,
  placeholder,
  lines,
  action,
}) {
  return (
    <section className="editor-panel" style={{ "--accent": color }}>
      <div className="panel-head">
        <div>
          <p>{title}</p>
          <h2>{subtitle}</h2>
        </div>
        <div className="panel-meta">
          <span>{lines} lines</span>
          {action}
        </div>
      </div>
      <textarea
        value={value}
        readOnly={readOnly}
        onChange={(event) => onChange?.(event.target.value)}
        placeholder={placeholder}
        spellCheck={false}
      />
    </section>
  );
}

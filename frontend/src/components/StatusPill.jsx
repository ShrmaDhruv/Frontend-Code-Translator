export function StatusPill({ label, value, color }) {
  return (
    <div className="status-pill" style={{ "--accent": color }}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

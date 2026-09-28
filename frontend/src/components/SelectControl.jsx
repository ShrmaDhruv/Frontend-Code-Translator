export function SelectControl({ label, value, options, onChange, color }) {
  return (
    <label className="select-control" style={{ "--accent": color }}>
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        style={{
          backgroundColor: color,
          color: "white"
        }}
      >
        {options.map((option) => (
          <option
            key={option}
            value={option}
            style={{
              backgroundColor: color,
              color: "white"
            }}
          >
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
import { API_BASE } from "../constants";

export async function runPipeline({
  code,
  sourceFramework,
  targetFramework,
}) {
  const response = await fetch(`${API_BASE}/api/pipeline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code,
      source_framework: sourceFramework,
      target_framework: targetFramework,
      use_llm_detection: true,
      stop_after: "translate",
    }),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(errorMessage(data.detail) || `Backend returned ${response.status}`);
  }

  return data;
}

export async function fetchHealth(signal) {
  const response = await fetch(`${API_BASE}/health`, { signal });
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
}

// FastAPI validation errors (422) return `detail` as a list of { loc, msg } objects.
function errorMessage(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "";
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .join("; ");
  }
  return typeof detail === "string" ? detail : "";
}

import { API_URL } from "../constants";

export async function runPipeline({
  code,
  sourceFramework,
  targetFramework,
}) {
  const response = await fetch(API_URL, {
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
    throw new Error(data.detail || `Backend returned ${response.status}`);
  }

  return data;
}

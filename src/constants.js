// export const API_URL = "http://127.0.0.1:8000/api/pipeline";
export const API_URL = "/api/pipeline";

export const SOURCE_OPTIONS = ["Auto Detect", "React", "Vue", "Angular", "HTML"];

export const TARGET_OPTIONS = ["React", "Vue", "Angular", "HTML"];

export const SAMPLE_CODE = `import React, { useState } from "react";

function ProductCard() {
  const [saved, setSaved] = useState(false);

  return (
    <section className="product-card">
      <p className="eyebrow">New collection</p>
      <h2>Orbit Desk Lamp</h2>
      <p>Warm dimming, brushed metal, and a compact base.</p>
      <button onClick={() => setSaved(!saved)}>
        {saved ? "Saved" : "Save item"}
      </button>
    </section>
  );
}

export default ProductCard;`;

export const FRAMEWORK_META = {
  React: { color: "#61dafb" },
  Vue: { color: "#42d392" },
  Angular: { color: "#f43f5e" },
  HTML: { color: "#fb923c" },
  "Auto Detect": { color: "#93c5fd" },
};

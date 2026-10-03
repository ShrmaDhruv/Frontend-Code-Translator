// The built UI is served by the backend, so it calls the API on its own origin.
// The Parcel dev server (port 1234) talks to a backend running locally on port 8000.
export const API_BASE = process.env.NODE_ENV === "production" ? "" : "http://127.0.0.1:8000";

export const AUTO_DETECT = "Auto Detect";

export const TARGET_OPTIONS = ["React", "Vue", "Angular", "HTML"];

export const SOURCE_OPTIONS = [AUTO_DETECT, ...TARGET_OPTIONS];

// Mirrors MAX_CODE_CHARS in backend/app/security/input_guard.py.
export const MAX_CODE_CHARS = 20000;

export const FRAMEWORK_META = {
  [AUTO_DETECT]: { label: "Auto", color: "#8b929c" },
  React: { label: "React", color: "#23b5e8" },
  Vue: { label: "Vue", color: "#42b883" },
  Angular: { label: "Angular", color: "#e8457a" },
  HTML: { label: "HTML", color: "#f0763a" },
};

export const PIPELINE_STEPS = [
  { id: "guard", label: "Guard" },
  { id: "detect", label: "Detect" },
  { id: "ir", label: "Extract IR" },
  { id: "translate", label: "Translate" },
  { id: "validate", label: "Validate" },
];

export const SAMPLES = {
  React: `import React, { useState } from "react";

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

export default ProductCard;`,

  Vue: `<script setup>
import { ref } from "vue";

const saved = ref(false);
</script>

<template>
  <section class="product-card">
    <p class="eyebrow">New collection</p>
    <h2>Orbit Desk Lamp</h2>
    <p>Warm dimming, brushed metal, and a compact base.</p>
    <button @click="saved = !saved">
      {{ saved ? "Saved" : "Save item" }}
    </button>
  </section>
</template>`,

  Angular: `import { Component } from "@angular/core";

@Component({
  selector: "app-product-card",
  standalone: true,
  template: \`
    <section class="product-card">
      <p class="eyebrow">New collection</p>
      <h2>Orbit Desk Lamp</h2>
      <p>Warm dimming, brushed metal, and a compact base.</p>
      <button (click)="toggleSaved()">
        {{ saved ? "Saved" : "Save item" }}
      </button>
    </section>
  \`,
})
export class ProductCardComponent {
  saved = false;

  toggleSaved() {
    this.saved = !this.saved;
  }
}`,

  HTML: `<section class="product-card">
  <p class="eyebrow">New collection</p>
  <h2>Orbit Desk Lamp</h2>
  <p>Warm dimming, brushed metal, and a compact base.</p>
  <button id="save-button">Save item</button>
</section>

<script>
  const button = document.getElementById("save-button");
  let saved = false;

  button.addEventListener("click", () => {
    saved = !saved;
    button.textContent = saved ? "Saved" : "Save item";
  });
</script>`,
};

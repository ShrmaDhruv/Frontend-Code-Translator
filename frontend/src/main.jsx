import React from "react";
import ReactDOM from "react-dom/client";

import "@fontsource-variable/geist";
import "@fontsource-variable/jetbrains-mono";

import App from "./App";
import { applyTheme, initialTheme } from "./hooks/useTheme";
import "./styles.css";

// Set before the first render so the page never flashes the wrong theme.
applyTheme(initialTheme());

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

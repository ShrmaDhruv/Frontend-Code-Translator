import React from "react";
import ReactDOM from "react-dom/client";

import TranslatorApp from "./src/App";
import "./src/styles.css";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <TranslatorApp />
  </React.StrictMode>
);

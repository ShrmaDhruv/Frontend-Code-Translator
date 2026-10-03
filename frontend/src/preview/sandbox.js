// Turns one component's source into the small project the Sandpack bundler runs:
// the component file, a fixed entry file that mounts it, an HTML page and a package.json.

const REACT_VERSION = "^19.0.0";
const VUE_VERSION = "^3.4.0";
// 18 is the last major where a component without a `standalone` flag belongs to an NgModule, which is
// the style the translator emits. It also supports standalone components, signals and @if / @for.
const ANGULAR_VERSION = "^18.2.0";

const BASE_STYLE = "body { margin: 0; padding: 20px; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; }";

// The bundler only keeps the <body> of index.html, so the entry file adds the page style itself.
const APPLY_BASE_STYLE = `const baseStyle = document.createElement("style");
baseStyle.textContent = ${JSON.stringify(BASE_STYLE)};
document.head.appendChild(baseStyle);
`;

const STYLE_IMPORT = /\.(css|scss|sass|less)$/;
const IMPORT_SPECIFIER = /(?:\bfrom\s*|\bimport\s*|\brequire\(\s*)["']([^"']+)["']/g;

function page(body) {
  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
  </head>
  <body>
    ${body}
  </body>
</html>`;
}

function packageName(specifier) {
  const parts = specifier.split("/");
  return specifier.startsWith("@") ? parts.slice(0, 2).join("/") : parts[0];
}

// Reads the component's imports: npm packages become dependencies, and relative
// stylesheet imports get an empty file so a missing .css does not break the build.
function scanImports(code, componentPath, provided, pinned = () => "latest") {
  const dependencies = { ...provided };
  const stubs = {};

  for (const [, specifier] of code.matchAll(IMPORT_SPECIFIER)) {
    if (specifier.startsWith(".")) {
      if (STYLE_IMPORT.test(specifier)) {
        stubs[new URL(specifier, `file://${componentPath}`).pathname] = { code: "" };
      }
    } else if (/^[@a-z]/i.test(specifier)) {
      const name = packageName(specifier);
      if (!(name in dependencies)) dependencies[name] = pinned(name);
    }
  }
  return { dependencies, stubs };
}

function packageJson(main, dependencies, devDependencies = {}) {
  return { code: JSON.stringify({ main, dependencies, devDependencies }, null, 2) };
}

function reactSandbox(code) {
  const componentPath = "/src/Component.tsx";
  const { dependencies, stubs } = scanImports(code, componentPath, {
    react: REACT_VERSION,
    "react-dom": REACT_VERSION,
  });

  return {
    template: "create-react-app",
    files: {
      ...stubs,
      "/package.json": packageJson("/src/index.js", dependencies),
      "/public/index.html": { code: page('<div id="root"></div>') },
      [componentPath]: { code },
      "/src/index.js": {
        code: `import React from "react";
import { createRoot } from "react-dom/client";
import * as Module from "./Component";

${APPLY_BASE_STYLE}
const isComponent = (value) => typeof value === "function" || (value && value.$$typeof);
const Component = Module.default || Object.values(Module).find(isComponent);

if (!isComponent(Component)) {
  throw new Error("No component export found. Add \`export default YourComponent\` to preview it.");
}

createRoot(document.getElementById("root")).render(<Component />);
`,
      },
    },
  };
}

function vueSandbox(code) {
  const componentPath = "/src/App.vue";
  const { dependencies, stubs } = scanImports(code, componentPath, { vue: VUE_VERSION });

  return {
    template: "vue-cli",
    files: {
      ...stubs,
      // The bundler reads the Vue CLI version to pick its Vue 3 single-file-component compiler.
      "/package.json": packageJson("/src/main.js", dependencies, {
        "@vue/cli-plugin-babel": "^5.0.8",
        "@vue/cli-service": "^5.0.8",
      }),
      "/public/index.html": { code: page('<div id="app"></div>') },
      [componentPath]: { code },
      "/src/main.js": {
        code: `import { createApp } from "vue";
import App from "./App.vue";

${APPLY_BASE_STYLE}
createApp(App).mount("#app");
`,
      },
    },
  };
}

function angularSelector(code) {
  const match = code.match(/selector\s*:\s*['"`]([^'"`]+)['"`]/);
  // Only element selectors can be written as a tag in index.html.
  return match && /^[a-z][\w-]*$/i.test(match[1]) ? match[1] : "ng-component";
}

// A classic component is declared in a module that brings the common directives (*ngIf, *ngFor, ngModel).
const ANGULAR_MODULE_BOOTSTRAP = `import { NgModule } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { BrowserModule } from "@angular/platform-browser";
import { platformBrowserDynamic } from "@angular/platform-browser-dynamic";

@NgModule({
  imports: [BrowserModule, FormsModule],
  declarations: [PreviewComponent],
  bootstrap: [PreviewComponent],
})
class PreviewModule {}

const started = platformBrowserDynamic().bootstrapModule(PreviewModule);`;

// A standalone component lists its own imports and is bootstrapped directly.
const ANGULAR_STANDALONE_BOOTSTRAP = `import { bootstrapApplication } from "@angular/platform-browser";

const started = bootstrapApplication(PreviewComponent);`;

function angularSandbox(code) {
  const componentPath = "/src/app/preview.component.ts";
  const selector = angularSelector(code);
  const isStandalone = /standalone\s*:\s*true/.test(code);
  const { dependencies, stubs } = scanImports(
    code,
    componentPath,
    {
      "@angular/common": ANGULAR_VERSION,
      "@angular/compiler": ANGULAR_VERSION,
      "@angular/core": ANGULAR_VERSION,
      "@angular/forms": ANGULAR_VERSION,
      "@angular/platform-browser": ANGULAR_VERSION,
      "@angular/platform-browser-dynamic": ANGULAR_VERSION,
      "core-js": "^3.30.0",
      rxjs: "^7.8.0",
      tslib: "^2.6.0",
      "zone.js": "~0.14.10",
    },
    (name) => (name.startsWith("@angular/") ? ANGULAR_VERSION : "latest"),
  );

  return {
    template: "angular-cli",
    files: {
      ...stubs,
      "/package.json": packageJson("/src/main.ts", dependencies),
      "/src/index.html": { code: page(`<${selector}></${selector}>`) },
      [componentPath]: { code },
      "/src/polyfills.ts": {
        code: `import "core-js/proposals/reflect-metadata";
import "zone.js";
`,
      },
      "/src/main.ts": {
        code: `import "./polyfills";
// Angular packages ship partially compiled; loading the compiler lets them finish compiling in the browser (JIT).
import "@angular/compiler";

import * as Module from "./app/preview.component";

${APPLY_BASE_STYLE}
const PreviewComponent: any = Object.values(Module).find((value) => typeof value === "function");

if (!PreviewComponent) {
  throw new Error("No component class found. Export the component class to preview it.");
}

${isStandalone ? ANGULAR_STANDALONE_BOOTSTRAP : ANGULAR_MODULE_BOOTSTRAP}

started.catch((error) => {
  // Rethrow outside the promise so the bundler reports it as a runtime error.
  setTimeout(() => {
    throw error;
  });
});
`,
      },
    },
  };
}

// The bundler treats index.html as markup only and never runs its <script> tags, so the entry
// file rebuilds the page: it copies the markup in, then re-creates each script so the browser runs it.
function htmlSandbox(code) {
  const isDocument = /<!doctype|<html[\s>]/i.test(code);

  return {
    template: "parcel",
    files: {
      "/package.json": packageJson("/index.js", {}),
      "/index.html": { code: page("") },
      "/index.js": {
        code: `const source = ${JSON.stringify(code)};
const parsed = new DOMParser().parseFromString(source, "text/html");

${isDocument ? "" : APPLY_BASE_STYLE}
for (const node of parsed.head.querySelectorAll("style, link[rel='stylesheet'], title")) {
  document.head.appendChild(document.importNode(node, true));
}
for (const attribute of parsed.body.attributes) {
  document.body.setAttribute(attribute.name, attribute.value);
}
document.body.innerHTML = parsed.body.innerHTML;

// Scripts inserted through innerHTML are inert; a freshly created element runs.
const scripts = [...parsed.head.querySelectorAll("script"), ...document.body.querySelectorAll("script")];
for (const original of scripts) {
  const script = document.createElement("script");
  for (const attribute of original.attributes) {
    script.setAttribute(attribute.name, attribute.value);
  }
  script.async = false;
  script.textContent = original.textContent;
  if (original.isConnected) {
    original.replaceWith(script);
  } else {
    document.head.appendChild(script);
  }
}

// The real page finished loading before this code ran, so replay the events scripts wait for.
document.dispatchEvent(new Event("DOMContentLoaded"));
window.dispatchEvent(new Event("load"));
`,
      },
    },
  };
}

const BUILDERS = {
  React: reactSandbox,
  Vue: vueSandbox,
  Angular: angularSandbox,
  HTML: htmlSandbox,
};

export function buildSandbox(framework, code) {
  return (BUILDERS[framework] || reactSandbox)(code);
}

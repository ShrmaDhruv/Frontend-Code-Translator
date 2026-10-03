import { useEffect, useRef, useState } from "react";

// Imported by file path: the package entry lazy-loads its clients with import(), which Parcel
// compiles to a bare chunk id that the browser cannot resolve.
import { SandpackRuntime } from "@codesandbox/sandpack-client/dist/clients/runtime/index.mjs";

import { buildSandbox } from "../preview/sandbox";

const DEBOUNCE_MS = 600;
const TIMEOUT_MS = 60000;

const CLIENT_OPTIONS = {
  showOpenInCodeSandbox: false,
  showErrorScreen: false,
  showLoadingScreen: false,
};

// The preview frame is served from a CodeSandbox origin, so the component cannot reach this page
// or the API. No allow-popups / allow-top-navigation: previewed code cannot open windows or
// navigate this tab away.
const IFRAME_SANDBOX = "allow-scripts allow-same-origin allow-forms allow-modals";

const STATUS_TEXT = {
  initializing: "Starting the bundler",
  "installing-dependencies": "Installing packages",
  transpiling: "Compiling",
  evaluating: "Running",
};

// The bundler reports Babel syntax errors wrapped in an unrelated TypeError; unwrap the real one.
const WRAPPED_ERROR = /^Cannot assign to read only property 'message' of object '(\w+): ([\s\S]*)'$/;

function readError(message) {
  const wrapped = WRAPPED_ERROR.exec(message.message || "");
  if (wrapped) return { title: wrapped[1], message: wrapped[2] };
  return { title: message.title, message: message.message, line: message.line };
}

const LOADING = { phase: "loading", detail: "Starting the bundler", error: null };

function useDebounced(value, delayMs) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export function Preview({ framework, code, emptyMessage }) {
  const iframeRef = useRef(null);
  const clientRef = useRef(null);
  const sentCodeRef = useRef("");
  const codeRef = useRef(code);
  const [state, setState] = useState(LOADING);
  const [consoleErrors, setConsoleErrors] = useState([]);
  const [reloads, setReloads] = useState(0);

  const debouncedCode = useDebounced(code, DEBOUNCE_MS);
  const hasCode = Boolean(code.trim());

  useEffect(() => {
    codeRef.current = code;
  }, [code]);

  // One bundler client per framework (and per manual reload).
  useEffect(() => {
    if (!hasCode) return undefined;

    setState(LOADING);
    setConsoleErrors([]);

    const timeout = window.setTimeout(() => {
      setState((current) =>
        current.phase === "loading"
          ? { phase: "error", detail: "", error: { title: "Preview timed out", message: "The preview service did not respond. Check your connection and reload the preview." } }
          : current,
      );
    }, TIMEOUT_MS);

    const onMessage = (message) => {
      if (message.type === "start") {
        setState(LOADING);
        setConsoleErrors([]);
      } else if (message.type === "status" && STATUS_TEXT[message.status]) {
        setState((current) => (current.phase === "loading" ? { ...current, detail: STATUS_TEXT[message.status] } : current));
      } else if (message.type === "action" && message.action === "show-error") {
        setState({ phase: "error", detail: "", error: readError(message) });
      } else if (message.type === "done") {
        setState((current) => (current.phase === "error" ? current : { phase: "ready", detail: "", error: null }));
      } else if (message.type === "console") {
        const errors = (message.log || [])
          .filter((entry) => entry.method === "error")
          .map((entry) => (entry.data || []).map(String).join(" "));
        if (errors.length > 0) setConsoleErrors((current) => [...current, ...errors].slice(-20));
      }
    };

    sentCodeRef.current = codeRef.current;
    const client = new SandpackRuntime(iframeRef.current, buildSandbox(framework, codeRef.current), CLIENT_OPTIONS);
    const unsubscribe = client.listen(onMessage);
    clientRef.current = client;

    return () => {
      window.clearTimeout(timeout);
      unsubscribe();
      client.destroy();
      clientRef.current = null;
    };
  }, [framework, hasCode, reloads]);

  // Push edits to the running bundler instead of restarting it.
  useEffect(() => {
    if (!clientRef.current || !debouncedCode.trim() || debouncedCode === sentCodeRef.current) return;
    sentCodeRef.current = debouncedCode;
    clientRef.current.updateSandbox(buildSandbox(framework, debouncedCode));
  }, [debouncedCode, framework]);

  if (!hasCode) {
    return <p className="empty">{emptyMessage}</p>;
  }

  const { phase, detail, error } = state;

  return (
    <div className="preview">
      <div className="preview-bar">
        <span className={`preview-status status-${phase}`}>
          <span className="health-dot" />
          {phase === "loading" && detail}
          {phase === "ready" && "Live"}
          {phase === "error" && "Error"}
        </span>
        <span className="preview-note">Runs in a sandboxed frame hosted by CodeSandbox</span>
        <button className="ghost-btn" onClick={() => setReloads((count) => count + 1)}>
          Reload
        </button>
      </div>

      <div className="preview-stage">
        <iframe
          key={`${framework}-${reloads}`}
          ref={iframeRef}
          className="preview-frame"
          title={`${framework} preview`}
          sandbox={IFRAME_SANDBOX}
        />
        {phase === "loading" && (
          <div className="preview-cover">
            <span className="spinner" />
            {detail}
          </div>
        )}
        {phase === "error" && (
          <div className="preview-error" role="alert">
            <strong>
              {error.title || "Error"}
              {error.line ? ` · line ${error.line}` : ""}
            </strong>
            <pre>{error.message}</pre>
          </div>
        )}
      </div>

      {consoleErrors.length > 0 && phase !== "error" && (
        <div className="preview-console">
          <strong>
            {consoleErrors.length} console error{consoleErrors.length > 1 ? "s" : ""}
          </strong>
          <pre>{consoleErrors[consoleErrors.length - 1]}</pre>
        </div>
      )}
    </div>
  );
}

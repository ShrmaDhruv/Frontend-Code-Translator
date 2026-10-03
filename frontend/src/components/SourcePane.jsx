import { useState } from "react";

import { AUTO_DETECT, FRAMEWORK_META, MAX_CODE_CHARS } from "../constants";
import { CodeEditor } from "./CodeEditor";
import { FrameworkIcon } from "./Icons";
import { Preview } from "./Preview";

const TABS = [
  { id: "code", label: "Code" },
  { id: "preview", label: "Preview" },
];

export function SourcePane({ source, language, code, onChange, onLoadSample, onClear, onRun }) {
  const [tab, setTab] = useState("code");
  const lines = code ? code.split("\n").length : 0;
  const overLimit = code.length > MAX_CODE_CHARS;
  const isAuto = source === AUTO_DETECT;

  return (
    <section className="pane" style={{ "--fw": FRAMEWORK_META[isAuto ? language : source].color }}>
      <div className="pane-head">
        <div className="pane-title">
          <span className="pane-kicker">Source</span>
          <span className="chip">
            <FrameworkIcon framework={isAuto ? language : source} size={14} />
            {isAuto ? `Auto · ${language}` : source}
          </span>
          <div className="tabs" role="tablist" aria-label="Source views">
            {TABS.map((item) => (
              <button
                key={item.id}
                role="tab"
                aria-selected={tab === item.id}
                className="tab"
                onClick={() => setTab(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="pane-tools">
          <span className={`meta ${overLimit ? "meta-over" : ""}`}>
            {lines} lines · {code.length.toLocaleString()} / {MAX_CODE_CHARS.toLocaleString()}
          </span>
          <button className="ghost-btn" onClick={onLoadSample}>
            Sample
          </button>
          <button className="ghost-btn" onClick={onClear} disabled={!code}>
            Clear
          </button>
        </div>
      </div>
      <div className="pane-body" role="tabpanel">
        {tab === "code" ? (
          <CodeEditor
            value={code}
            onChange={onChange}
            language={language}
            label="Source code"
            placeholder="Paste a component here..."
            onRun={onRun}
          />
        ) : (
          <Preview framework={language} code={code} emptyMessage="Paste a component to preview it." />
        )}
      </div>
    </section>
  );
}

import { useState } from "react";

import { FRAMEWORK_META } from "../constants";
import { CodeEditor } from "./CodeEditor";
import { ConfirmSource } from "./ConfirmSource";
import { DetectionView } from "./DetectionView";
import { CheckIcon, CopyIcon, FrameworkIcon } from "./Icons";
import { IRView } from "./IRView";
import { Preview } from "./Preview";

const TABS = [
  { id: "code", label: "Code" },
  { id: "preview", label: "Preview" },
  { id: "ir", label: "IR" },
  { id: "detection", label: "Detection" },
];

export function ResultPane({ target, code, run, tab, onTabChange, onCodeChange, onConfirmSource, onRun }) {
  const [copied, setCopied] = useState(false);
  const { result } = run;
  const isRunning = run.status === "running";
  const needsSource = result?.stage === "detect" && !result.ok;

  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  };

  return (
    <section className="pane" style={{ "--fw": FRAMEWORK_META[target].color }}>
      <div className="pane-head">
        <div className="pane-title">
          <span className="pane-kicker">Result</span>
          <span className="chip">
            <FrameworkIcon framework={target} size={14} />
            {target}
          </span>
          <div className="tabs" role="tablist" aria-label="Result views">
            {TABS.map((item) => (
              <button
                key={item.id}
                role="tab"
                aria-selected={tab === item.id}
                className="tab"
                onClick={() => onTabChange(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="pane-tools">
          {tab === "code" && (
            <>
              <span className="meta">{code ? code.split("\n").length : 0} lines</span>
              <button className="ghost-btn" onClick={copy} disabled={!code}>
                {copied ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
                {copied ? "Copied" : "Copy"}
              </button>
            </>
          )}
        </div>
      </div>

      <div className="pane-body" role="tabpanel">
        {tab === "code" && (
          <>
            <CodeEditor
              value={code}
              onChange={onCodeChange}
              language={target}
              label="Translated code"
              placeholder="The translated component appears here."
              onRun={onRun}
            />
            {isRunning && (
              <div className="overlay" aria-hidden="true">
                {[62, 38, 74, 51, 66, 29, 57, 44].map((width, index) => (
                  <span key={index} className="skeleton" style={{ width: `${width}%`, "--i": index }} />
                ))}
              </div>
            )}
            {needsSource && !isRunning && (
              <div className="overlay overlay-solid">
                <ConfirmSource detection={result.detection} onPick={onConfirmSource} />
              </div>
            )}
          </>
        )}
        {tab === "preview" && (
          <Preview
            framework={target}
            code={code}
            emptyMessage="Translate a component to preview the result."
          />
        )}
        {tab === "ir" && <IRView ir={result?.ir} />}
        {tab === "detection" && <DetectionView detection={result?.detection} />}
      </div>
    </section>
  );
}

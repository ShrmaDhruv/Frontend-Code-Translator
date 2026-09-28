import { useMemo, useState } from "react";

import { runPipeline } from "./api/pipeline";
import {
  FRAMEWORK_META,
  SAMPLE_CODE,
  SOURCE_OPTIONS,
  TARGET_OPTIONS,
} from "./constants";
import { ControlStrip } from "./components/ControlStrip";
import { StatusDock } from "./components/StatusDock";
import { TopBar } from "./components/TopBar";
import { Workspace } from "./components/Workspace";

export default function TranslatorApp() {
  const [sourceFramework, setSourceFramework] = useState("Auto Detect");
  const [targetFramework, setTargetFramework] = useState("Vue");
  const [inputCode, setInputCode] = useState(SAMPLE_CODE);
  const [outputCode, setOutputCode] = useState("");
  const [stage, setStage] = useState("idle");
  const [detected, setDetected] = useState("idle");
  const [confidence, setConfidence] = useState("idle");
  const [warnings, setWarnings] = useState([]);
  const [errors, setErrors] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [copyLabel, setCopyLabel] = useState("Copy");

  const sourceAccent = FRAMEWORK_META[sourceFramework]?.color || "#93c5fd";
  const targetAccent = FRAMEWORK_META[targetFramework]?.color || "#42d392";

  const editorStats = useMemo(
    () => ({
      inputLines: inputCode ? inputCode.split("\n").length : 0,
      outputLines: outputCode ? outputCode.split("\n").length : 0,
    }),
    [inputCode, outputCode],
  );

  const translateCode = async () => {
    const code = inputCode.trim();

    setErrors([]);
    setWarnings([]);
    setCopyLabel("Copy");

    if (!code) {
      setStage("error");
      setErrors(["Paste source code before running the pipeline."]);
      return;
    }

    setIsRunning(true);
    setStage("detecting");
    setDetected("detecting");
    setConfidence("idle");

    try {
      const data = await runPipeline({
        code: inputCode,
        sourceFramework,
        targetFramework,
      });

      setStage(data.stage || "done");
      setDetected(data.detection?.framework || data.source || "unknown");
      setConfidence(data.detection?.confidence || "unknown");
      setWarnings(data.warnings || []);
      setErrors(data.errors || []);
      setOutputCode(data.translated_code || "");

      if (data.ok && data.translated_code) {
        setStage("done");
      } else if (!data.ok) {
        setStage("error");
      }
    } catch (error) {
      setStage("error");
      const messages = [error.message];
      if (error.message === "Failed to fetch") {
        messages.push("Make sure the FastAPI backend is running on http://127.0.0.1:8000.");
      }
      setErrors(messages);
    } finally {
      setIsRunning(false);
    }
  };

  const copyOutput = async () => {
    if (!outputCode) return;

    await navigator.clipboard.writeText(outputCode);
    setCopyLabel("Copied");
    window.setTimeout(() => setCopyLabel("Copy"), 1400);
  };

  return (
    <div className="app-shell">
      <div className="page-glow page-glow-left" />
      <div className="page-glow page-glow-right" />

      <TopBar detected={detected} stage={stage} sourceAccent={sourceAccent} />

      <ControlStrip
        sourceFramework={sourceFramework}
        targetFramework={targetFramework}
        sourceAccent={sourceAccent}
        targetAccent={targetAccent}
        sourceOptions={SOURCE_OPTIONS}
        targetOptions={TARGET_OPTIONS}
        isRunning={isRunning}
        onSourceChange={setSourceFramework}
        onTargetChange={setTargetFramework}
        onTranslate={translateCode}
      />

      <Workspace
        sourceFramework={sourceFramework}
        targetFramework={targetFramework}
        sourceAccent={sourceAccent}
        targetAccent={targetAccent}
        inputCode={inputCode}
        outputCode={outputCode}
        inputLines={editorStats.inputLines}
        outputLines={editorStats.outputLines}
        copyLabel={copyLabel}
        onInputChange={setInputCode}
        onOutputChange={setOutputCode}
        onCopyOutput={copyOutput}
      />

      <StatusDock confidence={confidence} warnings={warnings} errors={errors} />
    </div>
  );
}

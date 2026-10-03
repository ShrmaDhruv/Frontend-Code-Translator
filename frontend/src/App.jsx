import { useCallback, useEffect, useRef, useState } from "react";

import { AUTO_DETECT, MAX_CODE_CHARS, SAMPLES, SOURCE_OPTIONS, TARGET_OPTIONS } from "./constants";
import { Header } from "./components/Header";
import { Notices } from "./components/Notices";
import { PipelineRail } from "./components/PipelineRail";
import { ResultPane } from "./components/ResultPane";
import { RouteBar } from "./components/RouteBar";
import { SourcePane } from "./components/SourcePane";
import { useHealth } from "./hooks/useHealth";
import { usePipeline } from "./hooks/usePipeline";
import { useTheme } from "./hooks/useTheme";

// Cheap guess used only to pick syntax highlighting before the backend has detected anything.
function guessFramework(code) {
  if (/<template[\s>]|<script\s+setup/.test(code)) return "Vue";
  if (/@Component\s*\(|@angular\//.test(code)) return "Angular";
  if (/^\s*<(?!>)/.test(code)) return "HTML";
  return "React";
}

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const health = useHealth();
  const { run, start, fail, reset } = usePipeline();

  const [source, setSource] = useState(AUTO_DETECT);
  const [target, setTarget] = useState("Vue");
  const [inputCode, setInputCode] = useState(SAMPLES.React);
  const [outputCode, setOutputCode] = useState("");
  const [tab, setTab] = useState("code");

  const isRunning = run.status === "running";
  const detected = TARGET_OPTIONS.includes(run.result?.detection?.framework)
    ? run.result.detection.framework
    : null;
  const sourceLanguage = source !== AUTO_DETECT ? source : detected || guessFramework(inputCode);

  const translate = useCallback(
    async (sourceOverride) => {
      if (isRunning) return;
      const sourceFramework = sourceOverride || source;

      setOutputCode("");
      setTab("code");

      if (!inputCode.trim()) {
        fail(["Paste some source code before translating."]);
        return;
      }
      if (inputCode.length > MAX_CODE_CHARS) {
        fail([`The source is longer than the ${MAX_CODE_CHARS.toLocaleString()} character limit.`]);
        return;
      }

      const data = await start({ code: inputCode, sourceFramework, targetFramework: target });
      if (data) setOutputCode(data.translated_code || "");
    },
    [fail, inputCode, isRunning, source, start, target],
  );

  // Ctrl/Cmd+Enter anywhere on the page; the editors handle it themselves and stop it bubbling.
  const translateRef = useRef(translate);
  useEffect(() => {
    translateRef.current = translate;
  }, [translate]);
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !event.defaultPrevented) {
        event.preventDefault();
        translateRef.current();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const confirmSource = (framework) => {
    setSource(framework);
    translate(framework);
  };

  const swapSource = source !== AUTO_DETECT ? source : detected;
  const swap = () => {
    if (!swapSource) return;
    setSource(target);
    setTarget(swapSource);
    if (outputCode) {
      setInputCode(outputCode);
      setOutputCode("");
    }
    reset();
  };

  const loadSample = () => {
    setInputCode(SAMPLES[sourceLanguage]);
    setOutputCode("");
    reset();
  };

  const clearInput = () => {
    setInputCode("");
    setOutputCode("");
    reset();
  };

  return (
    <div className="app">
      <Header health={health} theme={theme} onToggleTheme={toggleTheme} />

      <RouteBar
        source={source}
        target={target}
        sourceOptions={SOURCE_OPTIONS}
        targetOptions={TARGET_OPTIONS}
        isRunning={isRunning}
        canSwap={Boolean(swapSource)}
        onSourceChange={setSource}
        onTargetChange={setTarget}
        onSwap={swap}
        onTranslate={() => translate()}
      />

      <PipelineRail run={run} />

      <main className="workspace">
        <SourcePane
          source={source}
          language={sourceLanguage}
          code={inputCode}
          onChange={setInputCode}
          onLoadSample={loadSample}
          onClear={clearInput}
          onRun={() => translate()}
        />
        <ResultPane
          target={target}
          code={outputCode}
          run={run}
          tab={tab}
          onTabChange={setTab}
          onCodeChange={setOutputCode}
          onConfirmSource={confirmSource}
          onRun={() => translate()}
        />
      </main>

      <Notices errors={run.errors} warnings={run.warnings} />
    </div>
  );
}

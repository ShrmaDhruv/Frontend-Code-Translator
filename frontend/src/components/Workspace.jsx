import { EditorPanel } from "./EditorPanel";

export function Workspace({
  sourceFramework,
  targetFramework,
  sourceAccent,
  targetAccent,
  inputCode,
  outputCode,
  inputLines,
  outputLines,
  copyLabel,
  onInputChange,
  onOutputChange,
  onCopyOutput,
}) {
  return (
    <main className="workspace">
      <EditorPanel
        title="Input"
        subtitle={`${sourceFramework} source`}
        color={sourceAccent}
        value={inputCode}
        onChange={onInputChange}
        placeholder="Paste your frontend code here..."
        lines={inputLines}
      />

      <EditorPanel
        title="Output"
        subtitle={`${targetFramework} result`}
        color={targetAccent}
        value={outputCode}
        onChange={onOutputChange}
        placeholder="Translated code will appear here after the pipeline finishes..."
        lines={outputLines}
        action={
          <button className="ghost-btn" onClick={onCopyOutput} disabled={!outputCode}>
            {copyLabel}
          </button>
        }
      />
    </main>
  );
}

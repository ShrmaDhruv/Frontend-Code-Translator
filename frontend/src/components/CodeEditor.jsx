import { useEffect, useMemo, useRef } from "react";

import { html } from "@codemirror/lang-html";
import { javascript } from "@codemirror/lang-javascript";
import { vue } from "@codemirror/lang-vue";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { Prec } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import CodeMirror from "@uiw/react-codemirror";

const LANGUAGES = {
  React: javascript({ jsx: true, typescript: true }),
  Vue: vue(),
  Angular: javascript({ typescript: true }),
  HTML: html(),
};

// Colours come from CSS variables, so the editor follows the page theme.
const editorTheme = EditorView.theme({
  "&": { height: "100%", color: "var(--text)", backgroundColor: "transparent", fontSize: "13px" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--font-mono)", lineHeight: "1.7" },
  ".cm-content": { padding: "14px 0", caretColor: "var(--accent)" },
  ".cm-line": { padding: "0 16px 0 8px" },
  ".cm-gutters": { backgroundColor: "transparent", color: "var(--faint)", border: "none" },
  ".cm-lineNumbers .cm-gutterElement": { padding: "0 10px 0 16px", minWidth: "44px" },
  ".cm-activeLine": { backgroundColor: "var(--active-line)" },
  ".cm-activeLineGutter": { backgroundColor: "transparent", color: "var(--muted)" },
  ".cm-cursor": { borderLeftColor: "var(--accent)", borderLeftWidth: "2px" },
  "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground": {
    backgroundColor: "var(--selection)",
  },
  ".cm-matchingBracket, &.cm-focused .cm-matchingBracket": {
    backgroundColor: "var(--selection)",
    outline: "none",
  },
  ".cm-placeholder": { color: "var(--faint)" },
});

const highlightStyle = HighlightStyle.define([
  { tag: [t.keyword, t.modifier, t.operatorKeyword], color: "var(--syn-keyword)" },
  { tag: [t.string, t.special(t.string), t.regexp], color: "var(--syn-string)" },
  { tag: [t.number, t.bool, t.null, t.atom], color: "var(--syn-number)" },
  { tag: [t.comment, t.meta], color: "var(--syn-comment)", fontStyle: "italic" },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], color: "var(--syn-function)" },
  { tag: [t.tagName, t.angleBracket], color: "var(--syn-tag)" },
  { tag: t.attributeName, color: "var(--syn-attr)" },
  { tag: [t.typeName, t.className, t.namespace], color: "var(--syn-type)" },
  { tag: [t.propertyName, t.definition(t.propertyName)], color: "var(--syn-property)" },
  { tag: [t.operator, t.punctuation, t.separator, t.bracket], color: "var(--syn-punct)" },
]);

const BASIC_SETUP = {
  foldGutter: false,
  autocompletion: false,
  highlightSelectionMatches: false,
  tabSize: 2,
};

export function CodeEditor({ value, onChange, language, placeholder, label, onRun }) {
  const onRunRef = useRef(onRun);
  useEffect(() => {
    onRunRef.current = onRun;
  }, [onRun]);

  const extensions = useMemo(
    () => [
      editorTheme,
      syntaxHighlighting(highlightStyle),
      EditorView.contentAttributes.of({ "aria-label": label }),
      // Ctrl/Cmd+Enter runs the pipeline instead of inserting a blank line.
      Prec.highest(
        keymap.of([
          {
            key: "Mod-Enter",
            run: () => {
              onRunRef.current?.();
              return true;
            },
          },
        ]),
      ),
      LANGUAGES[language] || LANGUAGES.React,
    ],
    [language, label],
  );

  return (
    <CodeMirror
      className="code-editor"
      value={value}
      onChange={onChange}
      extensions={extensions}
      theme="none"
      height="100%"
      basicSetup={BASIC_SETUP}
      placeholder={placeholder}
    />
  );
}

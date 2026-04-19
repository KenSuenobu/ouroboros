"use client";

import { Editor } from "@monaco-editor/react";

interface Props {
  value: string;
  onChange: (value: string) => void;
  language?: string;
}

export function PromptEditor({ value, onChange, language = "markdown" }: Props) {
  return (
    <Editor
      value={value}
      defaultLanguage={language}
      theme="vs-dark"
      onChange={(v) => onChange(v || "")}
      options={{
        minimap: { enabled: false },
        wordWrap: "on",
        fontSize: 13,
        lineNumbers: "on",
        scrollBeyondLastLine: false,
      }}
    />
  );
}

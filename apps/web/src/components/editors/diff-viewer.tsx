"use client";

import { DiffEditor, Editor } from "@monaco-editor/react";

interface Props {
  original?: string;
  modified: string;
  language?: string;
  hidden?: boolean;
}

export function DiffViewer({ original, modified, language = "diff", hidden }: Props) {
  if (hidden) return <div style={{ display: "none" }} />;
  if (original === undefined || original === "") {
    return (
      <Editor
        defaultValue={modified}
        defaultLanguage={language}
        theme="vs-dark"
        options={{ readOnly: true, minimap: { enabled: false }, fontSize: 12 }}
      />
    );
  }
  return (
    <DiffEditor
      original={original}
      modified={modified}
      language={language}
      theme="vs-dark"
      options={{ readOnly: true, minimap: { enabled: false }, fontSize: 12 }}
    />
  );
}

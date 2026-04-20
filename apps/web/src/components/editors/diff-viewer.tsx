"use client";

import { DiffEditor } from "@monaco-editor/react";
import { useState } from "react";

interface Props {
  original?: string;
  modified: string;
  language?: string;
  hidden?: boolean;
  showModeToggle?: boolean;
}

export function DiffViewer({
  original = "",
  modified,
  language = "diff",
  hidden,
  showModeToggle = false,
}: Props) {
  const [renderSideBySide, setRenderSideBySide] = useState(true);

  if (hidden) return <div className="hidden" />;
  return (
    <div className="flex h-full min-h-0 flex-col">
      {showModeToggle ? (
        <div className="mb-2 flex justify-end">
          <button
            type="button"
            onClick={() => setRenderSideBySide((value) => !value)}
            className="rounded border border-zinc-700 px-2 py-1 text-xs text-zinc-100 hover:bg-zinc-800"
          >
            {renderSideBySide ? "Unified" : "Side-by-side"}
          </button>
        </div>
      ) : null}
      <div className="min-h-[160px] flex-1">
        <DiffEditor
          original={original}
          modified={modified}
          language={language}
          theme="vs-dark"
          options={{ readOnly: true, minimap: { enabled: false }, fontSize: 12, renderSideBySide }}
        />
      </div>
    </div>
  );
}

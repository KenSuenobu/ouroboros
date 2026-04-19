"""Overlay filesystem for dry-run mode.

write_file() lands in memory, read_file() prefers overlay then disk, diff() emits
a unified diff against the on-disk baseline so the UI can show what would happen.
"""

from __future__ import annotations

import difflib
from pathlib import Path


class VirtualFs:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._overlay: dict[str, str] = {}
        self._deleted: set[str] = set()

    def _abs(self, rel: str) -> Path:
        path = (self.root / rel).resolve()
        if not str(path).startswith(str(self.root)):
            raise PermissionError(f"path escapes sandbox: {rel}")
        return path

    def read_file(self, rel: str) -> str:
        if rel in self._deleted:
            raise FileNotFoundError(rel)
        if rel in self._overlay:
            return self._overlay[rel]
        path = self._abs(rel)
        return path.read_text("utf-8")

    def write_file(self, rel: str, content: str) -> None:
        self._overlay[rel] = content
        self._deleted.discard(rel)

    def delete_file(self, rel: str) -> None:
        self._deleted.add(rel)
        self._overlay.pop(rel, None)

    def list_changes(self) -> list[dict[str, str]]:
        changes: list[dict[str, str]] = []
        for rel, content in self._overlay.items():
            path = self._abs(rel)
            old = path.read_text("utf-8") if path.exists() else ""
            diff = "".join(
                difflib.unified_diff(
                    old.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"a/{rel}",
                    tofile=f"b/{rel}",
                )
            )
            changes.append({"path": rel, "kind": "modified" if path.exists() else "added", "diff": diff})
        for rel in self._deleted:
            changes.append({"path": rel, "kind": "deleted", "diff": ""})
        return changes

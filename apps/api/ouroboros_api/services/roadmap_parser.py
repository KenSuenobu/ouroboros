"""Parse FUTURE_FEATURE_ROADMAP_*.md / PLANNED_FEATURE_ROADMAP_*.md / ROADMAP*.md files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
ROADMAP_NAME_RE = re.compile(
    r"^(?P<kind>FUTURE_FEATURE_ROADMAP|PLANNED_FEATURE_ROADMAP|ROADMAP)(?:_.+)?\.md$",
    re.IGNORECASE,
)


@dataclass
class ParsedEntry:
    file_path: str
    section: str
    title: str
    body: str
    status: str
    kind: str


STATUS_HINTS = {
    "[done]": "done",
    "[x]": "done",
    "[in progress]": "in_progress",
    "[wip]": "in_progress",
    "[planned]": "planned",
    "[ ]": "planned",
}


def _classify_kind(filename: str) -> str:
    upper = filename.upper()
    if "FUTURE" in upper:
        return "future"
    if "PLANNED" in upper:
        return "planned"
    return "roadmap"


def _detect_status(line: str) -> str:
    lower = line.lower()
    for marker, status in STATUS_HINTS.items():
        if marker in lower:
            return status
    return "planned"


def parse_roadmap_file(path: Path) -> list[ParsedEntry]:
    text = path.read_text("utf-8", errors="ignore")
    entries: list[ParsedEntry] = []
    section_stack: list[tuple[int, str]] = []
    current_title: str | None = None
    current_body: list[str] = []
    current_status = "planned"
    kind = _classify_kind(path.name)

    def flush() -> None:
        nonlocal current_title, current_body, current_status
        if current_title is not None:
            section = " > ".join(s for _, s in section_stack[:-1]) if len(section_stack) > 1 else (section_stack[0][1] if section_stack else "")
            entries.append(
                ParsedEntry(
                    file_path=str(path),
                    section=section,
                    title=current_title,
                    body="\n".join(current_body).strip(),
                    status=current_status,
                    kind=kind,
                )
            )
        current_title = None
        current_body = []
        current_status = "planned"

    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            heading = m.group(2).strip()
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()
            section_stack.append((level, heading))
            current_title = heading
            current_status = _detect_status(line)
            continue
        if current_title is not None:
            current_body.append(line)
            if "status" in line.lower() or any(k in line.lower() for k in STATUS_HINTS):
                detected = _detect_status(line)
                if detected != "planned":
                    current_status = detected

    flush()
    return entries


def discover_roadmap_files(repo_root: Path) -> list[Path]:
    found: list[Path] = []
    for path in repo_root.rglob("*.md"):
        if any(part in {"node_modules", ".git", ".venv", "venv", "dist", "build"} for part in path.parts):
            continue
        if ROADMAP_NAME_RE.match(path.name):
            found.append(path)
    return sorted(found)

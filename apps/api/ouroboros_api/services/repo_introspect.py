"""Detect candidate build/test commands from common repo manifests."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import settings
from ..db.models import Project

_TARGET_FILES = ("package.json", "pyproject.toml", "Makefile", "Cargo.toml", "go.mod")


@dataclass(slots=True)
class RepoCommandSuggestions:
    build: list[str] = field(default_factory=list)
    test: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        return {"build": self.build, "test": self.test}


def _append_unique(values: list[str], value: str | None) -> None:
    if not value:
        return
    trimmed = value.strip()
    if trimmed and trimmed not in values:
        values.append(trimmed)


def _resolve_repo_root(project: Project) -> Path | None:
    if project.local_clone_hint:
        candidate = Path(project.local_clone_hint).expanduser()
        if candidate.exists():
            return candidate
    cached = settings.data_dir / "introspect-cache" / project.id
    if cached.exists() and (cached / ".git").exists():
        return cached
    return None


def _shallow_clone(project: Project) -> Path | None:
    target = settings.data_dir / "introspect-cache" / project.id
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)

    # protocol.file.allow=never requires Git >= 2.38.0 (Oct 2022)
    cmd = ["git", "-c", "protocol.file.allow=never", "clone", "--depth", "1"]
    if project.default_branch:
        cmd.extend(["--branch", project.default_branch])
    cmd.extend(["--", project.repo_url, str(target)])
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except Exception:
        if target.exists():
            shutil.rmtree(target)
        return None
    return target


def _safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_toml(path: Path) -> dict[str, Any]:
    import tomllib

    try:
        return tomllib.loads(_safe_read_text(path))
    except tomllib.TOMLDecodeError:
        return {}


def _normalize_test_script(script: str) -> str:
    parts = script.strip().split()
    if not parts:
        return script
    if parts[0] == "vitest" and "run" not in parts:
        return "vitest run"
    return script.strip()


def _suggest_from_package_json(path: Path, suggestions: RepoCommandSuggestions) -> None:
    try:
        data = json.loads(_safe_read_text(path))
    except json.JSONDecodeError:
        return
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return

    build_script = scripts.get("build")
    if isinstance(build_script, str):
        _append_unique(suggestions.build, build_script)
        _append_unique(suggestions.build, "npm run build")

    test_script = scripts.get("test")
    if isinstance(test_script, str):
        _append_unique(suggestions.test, _normalize_test_script(test_script))
        _append_unique(suggestions.test, "npm test")

    ci_test_script = scripts.get("test:ci")
    if isinstance(ci_test_script, str):
        _append_unique(suggestions.test, _normalize_test_script(ci_test_script))


def _suggest_from_pyproject(path: Path, suggestions: RepoCommandSuggestions) -> None:
    data = _load_toml(path)
    tool = data.get("tool")
    if isinstance(tool, dict) and isinstance(tool.get("pytest"), dict):
        _append_unique(suggestions.test, "uv run pytest -q")

    if isinstance(data.get("build-system"), dict):
        _append_unique(suggestions.build, "python -m build")


def _suggest_from_makefile(path: Path, suggestions: RepoCommandSuggestions) -> None:
    text = _safe_read_text(path)
    targets: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?![=])", line)
        if match:
            targets.add(match.group(1).lower())

    if "build" in targets:
        _append_unique(suggestions.build, "make build")
    if "test" in targets:
        _append_unique(suggestions.test, "make test")
    if "check" in targets:
        _append_unique(suggestions.test, "make check")


def _suggest_from_repo(root: Path) -> RepoCommandSuggestions:
    suggestions = RepoCommandSuggestions()

    package_json = root / "package.json"
    if package_json.exists():
        _suggest_from_package_json(package_json, suggestions)

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        _suggest_from_pyproject(pyproject, suggestions)

    makefile = root / "Makefile"
    if makefile.exists():
        _suggest_from_makefile(makefile, suggestions)

    if (root / "Cargo.toml").exists():
        _append_unique(suggestions.build, "cargo build")
        _append_unique(suggestions.test, "cargo test")

    if (root / "go.mod").exists():
        _append_unique(suggestions.build, "go build ./...")
        _append_unique(suggestions.test, "go test ./...")

    return suggestions


@dataclass(slots=True)
class RepoIntrospector:
    ttl_seconds: int = 3600
    _cache: dict[str, tuple[float, RepoCommandSuggestions]] = field(default_factory=dict)

    def introspect(self, project: Project) -> RepoCommandSuggestions:
        now = time.time()
        cache_key = project.id
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < self.ttl_seconds:
            return cached[1]

        root = _resolve_repo_root(project) or _shallow_clone(project)
        if root is None:
            result = RepoCommandSuggestions()
        else:
            result = _suggest_from_repo(root)
        self._cache[cache_key] = (now, result)
        return result

    def invalidate(self, project_id: str) -> None:
        self._cache.pop(project_id, None)


repo_introspector = RepoIntrospector()


def introspect_project_commands(project: Project) -> RepoCommandSuggestions:
    return repo_introspector.introspect(project)

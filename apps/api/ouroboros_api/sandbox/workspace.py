"""Per-run sandbox: fresh git clone in data/runs/<run_id>/repo."""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..config import settings


@dataclass
class RunSandbox:
    run_id: str
    root: Path
    repo_path: Path
    artifacts_path: Path
    logs_path: Path

    def cleanup(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)


async def prepare_sandbox(run_id: str, repo_url: str, branch: str = "main") -> RunSandbox:
    root = settings.runs_dir() / run_id
    repo_path = root / "repo"
    artifacts_path = root / "artifacts"
    logs_path = root / "logs"

    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    artifacts_path.mkdir(parents=True, exist_ok=True)
    logs_path.mkdir(parents=True, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        "git", "clone", "--depth", "50", "--branch", branch, repo_url, str(repo_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"git clone failed: {err.decode(errors='replace').strip() or out.decode(errors='replace').strip()}"
        )

    return RunSandbox(
        run_id=run_id,
        root=root,
        repo_path=repo_path,
        artifacts_path=artifacts_path,
        logs_path=logs_path,
    )

"""RunContext: the shared state passed to adapters + tool layer + builtins."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..db.models import Project, Run
from ..sandbox.virtual_fs import VirtualFs


@dataclass
class RunContext:
    workspace_id: str
    project_id: str
    run_id: str
    sandbox_path: Path
    vfs: VirtualFs
    dry_run: bool
    project: Project | None = None
    run: Run | None = None
    issue: dict[str, Any] | None = None
    scratchpad: dict[str, Any] = field(default_factory=dict)

    async def emit(self, event: str, payload: dict[str, Any]) -> None:
        from .events import RunEvent, bus

        await bus.publish(RunEvent(run_id=self.run_id, type=event, payload=payload))

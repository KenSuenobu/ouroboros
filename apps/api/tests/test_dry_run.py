"""Dry-run + side-effect classification guarantees."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from ouroboros_api.orchestrator.dry_run import is_dry_run, step_is_side_effecting
from ouroboros_api.sandbox.shell import classify_command, run_shell
from ouroboros_api.sandbox.virtual_fs import VirtualFs


def test_is_dry_run_inherits_from_run() -> None:
    run = SimpleNamespace(dry_run=True)
    assert is_dry_run(run) is True


def test_is_dry_run_inherits_from_agent() -> None:
    run = SimpleNamespace(dry_run=False)
    agent = SimpleNamespace(dry_run_default=True)
    assert is_dry_run(run, agent) is True


def test_is_dry_run_inherits_from_node_config() -> None:
    run = SimpleNamespace(dry_run=False)
    assert is_dry_run(run, None, {"config": {"dry_run": True}}) is True


def test_step_is_side_effecting_flag() -> None:
    assert step_is_side_effecting({"config": {"side_effecting": True}}) is True
    assert step_is_side_effecting({"config": {}}) is False
    assert step_is_side_effecting({}) is False


@pytest.mark.parametrize(
    "cmd, expected",
    [
        ("git push origin main", "side_effect"),
        ("gh pr create --fill", "side_effect"),
        ("npm publish", "side_effect"),
        ("sudo rm -rf /tmp/x", "side_effect"),
        ("npm run build", "build"),
        ("uv run pytest -q", "test"),
        ("ls -la", "read"),
        ("cat README.md", "read"),
        ("python -c 'print(1)'", "other"),
    ],
)
def test_classify_command(cmd: str, expected: str) -> None:
    assert classify_command(cmd) == expected


@pytest.mark.asyncio
async def test_run_shell_blocks_side_effect_in_dry_run(tmp_repo: Path) -> None:
    res = await run_shell("git push origin main", cwd=tmp_repo, dry_run=True)
    assert res.blocked is True
    assert res.classification == "side_effect"
    assert res.reason and "dry-run" in res.reason


@pytest.mark.asyncio
async def test_run_shell_allows_safe_commands(tmp_repo: Path) -> None:
    res = await run_shell("ls", cwd=tmp_repo, dry_run=True)
    assert res.blocked is False
    assert res.exit_code == 0
    assert "README.md" in res.stdout


def test_virtualfs_overlays_writes(tmp_repo: Path) -> None:
    vfs = VirtualFs(tmp_repo)
    vfs.write_file("src/app.py", "print('changed')\n")
    assert vfs.read_file("src/app.py") == "print('changed')\n"
    assert (tmp_repo / "src" / "app.py").read_text() == "print('ok')\n"


def test_virtualfs_lists_changes_with_diff(tmp_repo: Path) -> None:
    vfs = VirtualFs(tmp_repo)
    vfs.write_file("new.txt", "fresh\n")
    vfs.write_file("src/app.py", "print('changed')\n")
    vfs.delete_file("README.md")
    changes = {c["path"]: c for c in vfs.list_changes()}
    assert changes["new.txt"]["kind"] == "added"
    assert changes["src/app.py"]["kind"] == "modified"
    assert "print('changed')" in changes["src/app.py"]["diff"]
    assert changes["README.md"]["kind"] == "deleted"


def test_virtualfs_blocks_path_escape(tmp_repo: Path) -> None:
    vfs = VirtualFs(tmp_repo)
    with pytest.raises(PermissionError):
        vfs.read_file("../etc/passwd")

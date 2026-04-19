"""Sandbox: per-run isolated git clone + constrained shell + virtual FS for dry-run."""

from .shell import ShellResult, classify_command, run_shell
from .virtual_fs import VirtualFs
from .workspace import RunSandbox, prepare_sandbox

__all__ = [
    "RunSandbox",
    "ShellResult",
    "VirtualFs",
    "classify_command",
    "prepare_sandbox",
    "run_shell",
]

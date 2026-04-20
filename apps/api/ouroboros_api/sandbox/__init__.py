"""Sandbox: per-run isolated git clone + constrained shell + virtual FS for dry-run."""

from .shell import ShellResult, classify_command, iter_process_lines, run_shell, shell_line_subscriber
from .virtual_fs import VirtualFs
from .workspace import RunSandbox, prepare_sandbox

__all__ = [
    "RunSandbox",
    "ShellResult",
    "VirtualFs",
    "classify_command",
    "iter_process_lines",
    "prepare_sandbox",
    "run_shell",
    "shell_line_subscriber",
]

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .base import Executor


class CommandExecutor(Executor):
    """Run a target command directly and capture its process result."""

    def __init__(
        self,
        command: list[str],
        cwd: str | Path | None = None,
        timeout_seconds: float = 5.0,
        input_mode: str = "stdin",
        input_arg: str | None = None,
    ) -> None:
        self._command = list(command)
        self._cwd = str(cwd) if cwd is not None else None
        self._timeout_seconds = timeout_seconds
        self._input_mode = input_mode
        self._input_arg = input_arg

    def run(self, input_data: str | None = None) -> tuple[str, str, dict]:
        cmd = list(self._command)
        process_input = None

        if self._input_mode == "arg":
            if self._input_arg is not None:
                cmd.extend([self._input_arg, input_data or ""])
            else:
                cmd.append(input_data or "")
        else:
            process_input = input_data or ""

        started = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                cwd=self._cwd,
                input=process_input,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self._timeout_seconds,
            )
            return (
                result.stdout,
                result.stderr,
                {
                    "exit_code": result.returncode,
                    "timed_out": False,
                    "duration_s": time.monotonic() - started,
                    "command": cmd,
                },
            )
        except subprocess.TimeoutExpired as exc:
            return (
                exc.stdout or "",
                exc.stderr or "",
                {
                    "exit_code": None,
                    "timed_out": True,
                    "duration_s": time.monotonic() - started,
                    "command": cmd,
                },
            )

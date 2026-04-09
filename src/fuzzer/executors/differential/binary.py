"""Standalone executor for blackbox binary targets.

Runs a target binary by supplying the mutated input through a CLI flag
(default: ``--ipstr``) and returns captured process output.
"""

import os
import subprocess
from pathlib import Path
from typing import Any

from fuzzer.executors.base import ExecutionResult, Executor


class BinaryExecutor(Executor):
    """Execute a target binary as a subprocess.

    Parameters
    ----------
    binary_path:
        Path to the target executable.
    input_flag:
        CLI flag used to pass fuzz input. Defaults to ``--ipstr``.
    static_args:
        Optional extra arguments that should always be passed before
        the input flag.
    cwd:
        Optional working directory for the subprocess.
    timeout:
        Optional timeout (seconds) per run.
    env:
        Optional environment overrides for the subprocess.
    """

    def __init__(
        self,
        binary_path: str | Path,
        input_flag: str = "--ipstr",
        static_args: list[str] | None = None,
        cwd: str | Path | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.binary_path = Path(binary_path).resolve()
        self.input_flag = input_flag
        self.static_args = list(static_args or [])
        self.cwd = str(Path(cwd).resolve()) if cwd is not None else None
        self.timeout = timeout

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        self.env = merged_env

    def run(self, input_data: str | None = None) -> ExecutionResult[Any]:
        """Run binary once with *input_data* passed through ``input_flag``."""
        input_value = input_data or ""
        if self.input_flag.startswith("--"):
            # Use "--flag=value" so leading-hyphen fuzz inputs are parsed as values.
            input_arg = f"{self.input_flag}={input_value}"
            cmd = [
                str(self.binary_path),
                *self.static_args,
                input_arg,
            ]
        else:
            cmd = [
                str(self.binary_path),
                *self.static_args,
                self.input_flag,
                input_value,
            ]

        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.cwd,
                env=self.env,
                timeout=self.timeout,
                check=False,
            )
            return ExecutionResult(
                stdout=completed.stdout,
                stderr=completed.stderr,
                exit_code=completed.returncode,
                result=None,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
                exit_code=124,
                result=None,
            )
        except OSError as exc:
            return ExecutionResult(
                stdout="",
                stderr=str(exc),
                exit_code=1,
                result=None,
            )

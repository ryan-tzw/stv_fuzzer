import os
import subprocess
import tempfile
from pathlib import Path

from fuzzer.executors.base import ExecutionResult

from .base import (
    CoverageExecutorBase as _CoverageExecutorBase,
)


class PythonCoverageExecutor(_CoverageExecutorBase):
    """Spawn a fresh ``uv`` process that writes a temporary ``.coverage`` file."""

    def __init__(
        self,
        project_dir: str | Path,
        script_path: str | Path,
        script_args: list[str] | None = None,
    ):
        super().__init__(project_dir, script_path, script_args)

    def run(self, input_data: str | None = None) -> ExecutionResult[Path]:
        """Execute once; return stdout/stderr/exit code and coverage file path."""
        fd, coverage_path = tempfile.mkstemp(suffix=".coverage")
        os.close(fd)
        coverage_file = Path(coverage_path)

        env = self._prepare_env()

        cmd = self._build_uv_cmd(
            [
                "-m",
                "coverage",
                "run",
                "--branch",
                "--data-file",
                str(coverage_file),
                str(self.script_path),
                *self.script_args,
            ]
        )

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(self.project_dir),
            env=env,
            input=input_data,
        )

        return ExecutionResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            result=coverage_file,
        )

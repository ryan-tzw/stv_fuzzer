import json
import subprocess
from pathlib import Path

from fuzzer.executors.base import ExecutionResult

from .base import (
    _RUNNER_SCRIPT,
)
from .base import (
    CoverageExecutorBase as _CoverageExecutorBase,
)


class InProcessCoverageExecutor(_CoverageExecutorBase):
    """Use the runner shim to get coverage data via JSON, no temp file."""

    def __init__(
        self,
        project_dir: str | Path,
        script_path: str | Path,
        script_args: list[str] | None = None,
    ):
        super().__init__(project_dir, script_path, script_args)

    def run(self, input_data: str | None = None) -> ExecutionResult[dict]:
        """Return stdout/stderr/exit code and in-memory coverage dict."""
        env = self._prepare_env()

        cmd = self._build_uv_cmd(
            [
                str(_RUNNER_SCRIPT),
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

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            # Runner itself crashed before producing JSON; surface raw output.
            return ExecutionResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                result={},
            )

        return ExecutionResult(
            stdout=payload.get("stdout", ""),
            stderr=payload.get("stderr", ""),
            exit_code=int(payload.get("exit_code", result.returncode)),
            result=payload.get("coverage", {}),
        )

import json
import subprocess
from pathlib import Path

from .base import (
    _RUNNER_SCRIPT,
)
from .base import (
    CoverageExecutorBase as _CoverageExecutorBase,
)
from .base import (
    prepare_env as _prepare_env,
)
from .base import (
    uv_base_cmd as _uv_base_cmd,
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

    def run(self, input_data: str | None = None) -> tuple[str, str, int, dict]:
        """Return ``(stdout, stderr, exit_code, coverage_dict)``."""
        env = _prepare_env(self.project_dir)

        cmd = _uv_base_cmd(self.project_dir) + [
            str(_RUNNER_SCRIPT),
            str(self.script_path),
            *self.script_args,
        ]

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
            return result.stdout, result.stderr, result.returncode, {}

        return (
            payload.get("stdout", ""),
            payload.get("stderr", ""),
            int(payload.get("exit_code", result.returncode)),
            payload.get("coverage", {}),
        )

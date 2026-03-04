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


class PersistentCoverageExecutor(_CoverageExecutorBase):
    """Keep a single worker process running for repeated coverage runs."""

    def __init__(
        self,
        project_dir: str | Path,
        script_path: str | Path,
        script_args: list[str] | None = None,
        max_restarts: int = 5,
    ) -> None:
        from fuzzer.executors.worker import WorkerProcess

        super().__init__(project_dir, script_path, script_args)

        env = _prepare_env(self.project_dir)

        cmd = _uv_base_cmd(self.project_dir) + [
            str(_RUNNER_SCRIPT),
            "--loop",
            str(self.script_path),
            *self.script_args,
        ]

        self._worker = WorkerProcess(
            cmd=cmd,
            env=env,
            cwd=str(self.project_dir),
            max_restarts=max_restarts,
        )

    def start(self) -> None:
        """Start the worker process."""
        self._worker.start()

    def stop(self) -> None:
        """Terminate the worker."""
        self._worker.stop()

    def run(self, input_data: str | None = None) -> tuple[str, str, dict]:
        """Execute via worker and return ``(stdout, stderr, coverage)``."""
        payload = self._worker.send({"input": input_data})

        if "_worker_error" in payload:
            return "", payload.get("_stderr", ""), {}

        return (
            payload.get("stdout", ""),
            payload.get("stderr", ""),
            payload.get("coverage", {}),
        )

    def __enter__(self) -> "PersistentCoverageExecutor":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

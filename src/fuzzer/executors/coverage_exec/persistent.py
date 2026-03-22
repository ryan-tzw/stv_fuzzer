from pathlib import Path
from typing import cast

from fuzzer.executors.base import ExecutionResult

from .base import (
    _RUNNER_SCRIPT,
)
from .base import (
    CoverageExecutorBase as _CoverageExecutorBase,
)
from .types import CoveragePayload


class PersistentCoverageExecutor(_CoverageExecutorBase):
    """Keep a single worker process running for repeated coverage runs."""

    def __init__(
        self,
        project_dir: str | Path,
        script_path: str | Path,
        script_args: list[str] | None = None,
        max_restarts: int = 5,
    ) -> None:
        from fuzzer.executors.worker_process import WorkerProcess

        super().__init__(project_dir, script_path, script_args)

        env = self._prepare_env()

        cmd = self._build_uv_cmd(
            [
                str(_RUNNER_SCRIPT),
                "--loop",
                str(self.script_path),
                *self.script_args,
            ]
        )

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

    def run(self, input_data: str | None = None) -> ExecutionResult[CoveragePayload]:
        """Execute via worker and return stdout/stderr/exit code and coverage."""
        from fuzzer.executors.worker_process import WorkerCrashedError

        try:
            payload = self._worker.send({"input": input_data})
        except WorkerCrashedError as exc:
            return ExecutionResult(
                stdout="",
                stderr=str(exc),
                exit_code=1,
                result=cast(CoveragePayload, {}),
            )

        if "_worker_error" in payload:
            return ExecutionResult(
                stdout="",
                stderr=payload.get("_stderr", ""),
                exit_code=1,
                result=cast(CoveragePayload, {}),
            )

        return ExecutionResult(
            stdout=payload.get("stdout", ""),
            stderr=payload.get("stderr", ""),
            exit_code=int(payload.get("exit_code", 0)),
            result=cast(CoveragePayload, payload.get("coverage", {})),
        )

    def __enter__(self) -> "PersistentCoverageExecutor":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

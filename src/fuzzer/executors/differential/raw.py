"""Simple executor that runs a command with given stdin and returns output."""

from pathlib import Path
from subprocess import PIPE, run
from typing import List, Optional

from fuzzer.executors.executor_types import ExecutorResult
from fuzzer.executors.worker import WorkerProcess

_RAW_RUNNER_SCRIPT = Path(__file__).parent.parent / "_raw_persistent_runner.py"


def _persistent_worker_cmd(
    cmd: list[str],
) -> tuple[list[str], str | None] | None:
    """Build a worker command for supported Python-script invocation forms.

    Supported:
    - ``uv run --project <dir> ... python <script> [args...]``
    - ``python <script> [args...]``
    """
    if not cmd:
        return None

    if cmd[0] == "uv" and len(cmd) >= 6 and cmd[1] == "run":
        try:
            proj_idx = cmd.index("--project")
            project_dir = cmd[proj_idx + 1]
        except ValueError, IndexError:
            return None

        py_idx = next(
            (i for i, part in enumerate(cmd) if part.startswith("python")), -1
        )
        if py_idx == -1 or py_idx + 1 >= len(cmd):
            return None

        script_and_args = cmd[py_idx + 1 :]
        worker_cmd = cmd[: py_idx + 1] + [
            str(_RAW_RUNNER_SCRIPT),
            "--loop",
            *script_and_args,
        ]
        return worker_cmd, project_dir

    if cmd[0].startswith("python") and len(cmd) >= 2:
        worker_cmd = [cmd[0], str(_RAW_RUNNER_SCRIPT), "--loop", *cmd[1:]]
        return worker_cmd, None

    return None


class RawProcessExecutor:
    """Execute an arbitrary command without coverage, returning stdout/stderr.

    Intended as the blackbox side of a differential executor; not used
    standalone by the fuzzing engine.
    """

    def __init__(
        self,
        cmd: List[str],
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        max_restarts: int = 5,
    ) -> None:
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self._worker: WorkerProcess | None = None

        persistent_spec = _persistent_worker_cmd(cmd)
        if persistent_spec is not None:
            worker_cmd, worker_cwd = persistent_spec
            self._worker = WorkerProcess(
                cmd=worker_cmd,
                env=env,
                cwd=cwd or worker_cwd,
                max_restarts=max_restarts,
            )

    def run(self, input_data: str | None = None) -> ExecutorResult:
        """Run the command, feeding *input_data* to stdin.

        Returns an ExecutorResult.
        """
        if self._worker is not None:
            payload = self._worker.send({"input": input_data})
            if "_worker_error" in payload:
                return ExecutorResult(
                    stdout="",
                    stderr=payload.get("_stderr", ""),
                    return_code=-1,
                    raw_coverage={},
                    diff_kind="executor_failure",
                )

            return ExecutorResult(
                stdout=payload.get("stdout", ""),
                stderr=payload.get("stderr", ""),
                return_code=int(payload.get("exit_code", 0)),
                raw_coverage={},
            )

        result = run(
            self.cmd,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
            cwd=self.cwd,
            env=self.env,
            input=input_data,
        )
        return ExecutorResult(
            stdout=result.stdout,
            stderr=result.stderr,
            return_code=result.returncode,
            raw_coverage={},
        )

    def start(self) -> None:
        if self._worker is not None:
            self._worker.start()

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()

"""
Runs a harness script under coverage.py inside the target's uv environment.

Three executor variants are provided:

* PythonCoverageExecutor
    Original implementation; writes a temp .coverage file that the observer
    reads back from disk.

* InProcessCoverageExecutor
    Removes the file I/O bottleneck: uses a runner shim that keeps coverage
    in-memory and returns results as JSON over stdout.  Still spawns a fresh
    subprocess per iteration, so ``uv`` / Python startup cost is paid each
    time.

* PersistentCoverageExecutor
    Eliminates subprocess startup overhead by keeping a single long-lived
    worker process alive for the lifetime of the executor (via
    :class:`~fuzzer.executors.worker.WorkerProcess`).  The worker runs the
    runner shim in ``--loop`` mode, so only the harness execution and
    coverage measurement happen per iteration.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .coverage_base import (
    _RUNNER_SCRIPT,
)
from .coverage_base import (
    CoverageExecutorBase as _CoverageExecutorBase,
)
from .coverage_base import (
    prepare_env as _prepare_env,
)
from .coverage_base import (
    uv_base_cmd as _uv_base_cmd,
)

__all__ = [
    "PythonCoverageExecutor",
    "InProcessCoverageExecutor",
    "PersistentCoverageExecutor",
]


class PythonCoverageExecutor(_CoverageExecutorBase):
    def __init__(
        self,
        project_dir: str | Path,
        script_path: str | Path,
        script_args: list[str] | None = None,
    ):
        super().__init__(project_dir, script_path, script_args)

    def run(self, input_data: str | None = None) -> tuple[str, str, Path]:
        """
        Run the harness under coverage.py in the target's uv environment.
        If *input_data* is provided, it is passed to the harness via stdin.

        Returns ``(stdout, stderr, coverage_file_path)``.  This signature
        matches the base :class:`Executor` contract (``result`` is a ``Path``).
        """
        fd, coverage_path = tempfile.mkstemp(suffix=".coverage")
        os.close(fd)
        coverage_file = Path(coverage_path)

        env = _prepare_env(self.project_dir)

        cmd = _uv_base_cmd(self.project_dir) + [
            "-m",
            "coverage",
            "run",
            "--branch",
            "--data-file",
            str(coverage_file),
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

        return result.stdout, result.stderr, coverage_file


# --------------------------------------------------------------------------- #
#  In-process (no-file) variant                                             #
# --------------------------------------------------------------------------- #


class InProcessCoverageExecutor(_CoverageExecutorBase):
    """
    Run a harness under coverage.py **without writing any .coverage file**.

    The executor delegates to ``_inprocess_runner.py``, a shim that starts
    coverage in-memory (``data_file=False``), runs the harness via
    ``runpy.run_path()``, then serialises the combined result as a single
    JSON line on stdout::

        {
            "stdout":    "<harness stdout>",
            "stderr":    "<harness stderr>",
            "exit_code": <int>,
            "coverage":  {"<abs_path>": {"lines": [...], "arcs": [...]}}
        }

    :meth:`run` returns ``(harness_stdout, harness_stderr, coverage_dict)``
    where *coverage_dict* is the parsed inner ``"coverage"`` mapping.
    This replaces the ``Path`` returned by :class:`PythonCoverageExecutor`
    so no observer clean-up step is needed.
    """

    def __init__(
        self,
        project_dir: str | Path,
        script_path: str | Path,
        script_args: list[str] | None = None,
    ):
        super().__init__(project_dir, script_path, script_args)

    def run(self, input_data: str | None = None) -> tuple[str, str, dict]:
        """
        Run the harness under in-memory coverage in the target's uv environment.

        If *input_data* is provided it is passed to the harness via stdin.
        Returns ``(harness_stdout, harness_stderr, coverage_dict)``.
        No temporary files are created or deleted.

        The return type satisfies the :class:`Executor` interface; the third
        element is a generic ``dict`` rather than a path since no file is
        involved.
        """
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
            return result.stdout, result.stderr, {}

        return (
            payload.get("stdout", ""),
            payload.get("stderr", ""),
            payload.get("coverage", {}),
        )


# --------------------------------------------------------------------------- #
#  Persistent worker variant                                                  #
# --------------------------------------------------------------------------- #


class PersistentCoverageExecutor(_CoverageExecutorBase):
    """
    Run a harness under coverage.py using a **single long-lived worker**.

    On the first call to :meth:`run` (or on :meth:`start`) a subprocess is
    spawned running ``_inprocess_runner.py --loop``.  All subsequent calls
    send a JSON request over stdin and read a JSON response over stdout,
    paying only the cost of harness execution + coverage measurement rather
    than full subprocess + ``uv`` startup on every iteration.

    Crash recovery is delegated to :class:`~fuzzer.executors.worker.WorkerProcess`:
    if the worker crashes it is automatically restarted (up to *max_restarts*
    times) and the failed iteration returns an empty coverage dict so the
    fuzzing loop can continue.

    .. note::
        Because the target package remains in ``sys.modules`` across iterations
        inside the worker, module-level side effects (global state, caches, etc.)
        persist between runs.  For stateless harnesses this has no impact.

    Parameters
    ----------
    project_dir:
        Root of the target ``uv`` project.
    script_path:
        Path to the harness script.
    script_args:
        Extra arguments forwarded to the harness.
    max_restarts:
        How many worker crashes to tolerate before raising
        :class:`~fuzzer.executors.worker.WorkerCrashedError`.
    """

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
        """Explicitly start the worker (also called lazily on first :meth:`run`)."""
        self._worker.start()

    def stop(self) -> None:
        """Shut down the worker process."""
        self._worker.stop()

    def run(self, input_data: str | None = None) -> tuple[str, str, dict]:
        """
        Send *input_data* to the persistent worker and return
        ``(harness_stdout, harness_stderr, coverage_dict)``.

        If the worker crashed and was restarted, the returned tuple will contain
        an empty coverage dict and the stderr captured from the failed
        invocation.  This behaviour is described in the :class:`Executor`
        contract via the ``result`` element being ``Any``.
        """
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

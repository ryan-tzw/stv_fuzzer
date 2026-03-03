"""
Generic persistent worker process.

``WorkerProcess`` manages a long-lived subprocess that speaks a
newline-delimited JSON protocol over its stdin/stdout:

    Executor → Worker  (stdin):   one JSON object per line (a request)
    Worker   → Executor (stdout): one JSON object per line (a response)

The subprocess is responsible for looping and handling requests; this
class handles the lifecycle (lazy startup, crash detection, restart).

Any harness runner that reads JSON from stdin and writes JSON to stdout
in a loop is compatible with this driver — coverage, binary harnesses,
remote proxies, etc.

Typical usage::

    worker = WorkerProcess(cmd=[...], env={...}, cwd="...")
    # Lazy-started on the first send(); or call start() explicitly.

    response = worker.send({"input": "..."})

    worker.stop()

Context-manager form::

    with WorkerProcess(cmd=[...]) as worker:
        response = worker.send({"input": "..."})
"""

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class WorkerCrashedError(RuntimeError):
    """Raised when the worker process crashes and cannot be restarted."""


class WorkerProcess:
    """
    Drive a persistent subprocess over a newline-delimited JSON protocol.

    Parameters
    ----------
    cmd:
        Full command used to launch the worker (passed directly to
        ``subprocess.Popen``).
    env:
        Environment for the child process.  ``None`` inherits the current
        process environment.
    cwd:
        Working directory for the child process.
    max_restarts:
        How many times the worker may be restarted after a crash before
        :meth:`send` raises :class:`WorkerCrashedError`.  Use ``-1`` for
        unlimited restarts.
    """

    def __init__(
        self,
        cmd: list[str],
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        max_restarts: int = 5,
    ) -> None:
        self._cmd = cmd
        self._env = env
        self._cwd = cwd
        self._max_restarts = max_restarts
        self._restarts = 0
        self._proc: subprocess.Popen | None = None

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Launch the worker subprocess (no-op if already alive)."""
        if self.is_alive():
            return
        self._proc = subprocess.Popen(
            self._cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env,
            cwd=self._cwd,
            text=True,
            bufsize=1,  # line-buffered
        )
        logger.debug("WorkerProcess started (pid=%d): %s", self._proc.pid, self._cmd)

    def stop(self) -> None:
        """
        Ask the worker to exit gracefully, then wait for it.

        Sends ``{"cmd": "exit"}`` over stdin; if the process does not
        terminate within 3 seconds it is forcibly killed.
        """
        if not self.is_alive():
            return
        if self._proc is None:
            return
        try:
            assert self._proc.stdin is not None
            self._proc.stdin.write(json.dumps({"cmd": "exit"}) + "\n")
            self._proc.stdin.flush()
            self._proc.stdin.close()
            self._proc.wait(timeout=3)
        except Exception:
            self._proc.kill()
            self._proc.wait()
        finally:
            self._proc = None

    def is_alive(self) -> bool:
        """Return ``True`` if the worker subprocess is running."""
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------ #
    #  Communication                                                       #
    # ------------------------------------------------------------------ #

    def send(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Send *request* to the worker and return its response.

        If the worker is not yet started it is launched lazily.
        If the worker crashes mid-request it is restarted (up to
        ``max_restarts`` times) and the caller receives an error dict
        ``{"_worker_error": "crashed", "_restarts": N}`` for that single
        request so the fuzzing loop can continue.

        Raises
        ------
        WorkerCrashedError
            When the worker crashes more than ``max_restarts`` times.
        """
        if not self.is_alive():
            self.start()

        return self._send_once(request)

    def _send_once(self, request: dict[str, Any]) -> dict[str, Any]:
        """Inner send; restarts the worker on crash and retries once."""
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("WorkerProcess is not running")
        try:
            line = json.dumps(request) + "\n"
            self._proc.stdin.write(line)
            self._proc.stdin.flush()

            response_line = self._proc.stdout.readline()
            if not response_line:
                raise EOFError("Worker closed stdout without a response")

            return json.loads(response_line)

        except (BrokenPipeError, EOFError, json.JSONDecodeError) as exc:
            return self._handle_crash(exc, request)

    def _handle_crash(
        self, exc: Exception, original_request: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle a worker crash: kill the old process, restart if allowed."""
        stderr_tail = ""
        if self._proc is not None:
            try:
                self._proc.kill()
                _, stderr_tail = self._proc.communicate(timeout=2)
            except Exception:
                pass
            self._proc = None

        self._restarts += 1
        logger.warning(
            "WorkerProcess crashed (%s); restart %d/%s. stderr tail: %s",
            exc,
            self._restarts,
            "∞" if self._max_restarts == -1 else self._max_restarts,
            stderr_tail[-500:] if stderr_tail else "(none)",
        )

        if self._max_restarts != -1 and self._restarts > self._max_restarts:
            raise WorkerCrashedError(
                f"Worker crashed {self._restarts} times (limit={self._max_restarts})"
            ) from exc

        self.start()
        return {
            "_worker_error": "crashed",
            "_restarts": self._restarts,
            "_stderr": stderr_tail,
        }

    # ------------------------------------------------------------------ #
    #  Context manager                                                     #
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "WorkerProcess":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def __del__(self) -> None:
        # Best-effort cleanup when the object is GC'd without explicit stop().
        try:
            self.stop()
        except Exception:
            pass

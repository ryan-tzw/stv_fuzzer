"""Persistent subprocess wrapper using a JSON protocol.

WorkerProcess starts a long-lived child and exchanges newline-delimited
JSON messages (request on stdin, response on stdout).  It's generic and can
drive anything that speaks the protocol.  The object handles restarts and
cleanup; :class:`WorkerCrashedError` is raised if crashes exceed the limit.
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
    Manage a subprocess that speaks NDJSON over stdin/stdout.

    ``cmd`` is passed to ``Popen``; ``max_restarts`` limits automatic
    recovery.  ``env`` and ``cwd`` control the child's environment.
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
        """Low-level send with one automatic restart on crash."""
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
        """Manage crash bookkeeping and optionally restart the worker."""
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

"""Crash detection strategies used by the fuzzing engine."""

import re
from abc import ABC, abstractmethod


class CrashDetector(ABC):
    """Determine whether an execution should be classified as a crash."""

    @abstractmethod
    def is_crash(
        self,
        exit_code: int | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> bool:
        """Return True when the execution output indicates a crash."""
        ...


class ExitCodeCrashDetector(CrashDetector):
    """Classify any non-zero exit code as a crash."""

    def is_crash(
        self,
        exit_code: int | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> bool:
        if exit_code is None:
            return False
        return exit_code != 0


class StderrPrefixCrashDetector(CrashDetector):
    """Crash detector based on a marker string in stderr."""

    def __init__(self, prefix: str = "ERR:") -> None:
        self.prefix = prefix

    def is_crash(
        self,
        exit_code: int | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> bool:
        return self.prefix in stderr


class ExitCodeOrOutputCrashDetector(CrashDetector):
    """Treat non-zero exits or known bug markers in output as crashes."""

    _GENERIC_BUG_MARKER_RE = re.compile(
        r"\bbug has been triggered\b|traceback \(most recent call last\)",
        flags=re.IGNORECASE,
    )
    _FINAL_BUG_COUNT_NONEMPTY_RE = re.compile(
        r"final bug count\s*:\s*.*\{[^}]*\([^)]*\)[^}]*\}",
        flags=re.IGNORECASE | re.DOTALL,
    )

    def is_crash(
        self,
        exit_code: int | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> bool:
        if exit_code is not None and exit_code != 0:
            return True

        combined = f"{stdout}\n{stderr}"
        if self._GENERIC_BUG_MARKER_RE.search(combined):
            return True

        return bool(self._FINAL_BUG_COUNT_NONEMPTY_RE.search(combined))

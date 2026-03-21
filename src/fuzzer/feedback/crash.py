"""Crash detection strategies used by the fuzzing engine."""

from abc import ABC, abstractmethod


class CrashDetector(ABC):
    """Determine whether an execution should be classified as a crash."""

    @abstractmethod
    def is_crash(self, exit_code: int | None = None, stderr: str = "") -> bool:
        """Return True when the execution output indicates a crash."""
        ...


class ExitCodeCrashDetector(CrashDetector):
    """Classify any non-zero exit code as a crash."""

    def is_crash(self, exit_code: int | None = None, stderr: str = "") -> bool:
        if exit_code is None:
            return False
        return exit_code != 0


class StderrPrefixCrashDetector(CrashDetector):
    """Crash detector based on a marker string in stderr."""

    def __init__(self, prefix: str = "ERR:") -> None:
        self.prefix = prefix

    def is_crash(self, exit_code: int | None = None, stderr: str = "") -> bool:
        return self.prefix in stderr

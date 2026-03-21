"""Crash detection strategies used by the fuzzing engine."""

from abc import ABC, abstractmethod


class CrashDetector(ABC):
    """Determine whether an execution should be classified as a crash."""

    @abstractmethod
    def is_crash(self, stderr: str = "") -> bool:
        """Return True when the execution output indicates a crash."""
        ...


class StderrPrefixCrashDetector(CrashDetector):
    """Crash detector based on a marker string in stderr."""

    def __init__(self, prefix: str = "ERR:") -> None:
        self.prefix = prefix

    def is_crash(self, stderr: str = "") -> bool:
        return self.prefix in stderr

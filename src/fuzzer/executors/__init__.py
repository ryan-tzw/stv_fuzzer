"""Public API for the ``fuzzer.executors`` package."""

from .base import ExecutionResult, Executor
from .coverage_exec.persistent import PersistentCoverageExecutor

__all__ = [
    "ExecutionResult",
    "Executor",
    "PersistentCoverageExecutor",
]

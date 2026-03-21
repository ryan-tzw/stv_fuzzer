"""Public API for the ``fuzzer.executors`` package."""

from .base import ExecutionResult, Executor
from .coverage_exec.persistent import PersistentCoverageExecutor
from .differential.binary import BinaryExecutor

__all__ = [
    "BinaryExecutor",
    "ExecutionResult",
    "Executor",
    "PersistentCoverageExecutor",
]

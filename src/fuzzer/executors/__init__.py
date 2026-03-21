"""Public API for the ``fuzzer.executors`` package."""

from .base import ExecutionResult, Executor
from .coverage_exec.file_executor import PythonCoverageExecutor
from .coverage_exec.inprocess import InProcessCoverageExecutor
from .coverage_exec.persistent import PersistentCoverageExecutor

__all__ = [
    "ExecutionResult",
    "Executor",
    "PythonCoverageExecutor",
    "InProcessCoverageExecutor",
    "PersistentCoverageExecutor",
]

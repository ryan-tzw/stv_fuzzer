"""Public API for the ``fuzzer.executors`` package."""

from .base import ExecutionResult, Executor
from .differential.binary import BinaryExecutor
from .coverage_exec.persistent import PersistentCoverageExecutor
from .differential import DifferentialExecutor, DifferentialResult

__all__ = [
    "BinaryExecutor",
    "DifferentialExecutor",
    "DifferentialResult",
    "ExecutionResult",
    "Executor",
    "PersistentCoverageExecutor",
]

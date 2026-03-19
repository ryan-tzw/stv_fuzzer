"""Public API for the ``fuzzer.executors`` package."""

from .base import Executor
from .coverage_exec.file_executor import PythonCoverageExecutor
from .coverage_exec.inprocess import InProcessCoverageExecutor
from .coverage_exec.persistent import PersistentCoverageExecutor
from .differential import DifferentialExecutor, RawProcessExecutor
from .types import DiffKind, ExecutorResult, RawArc, RawCoverageFile, RawCoverageMap

__all__ = [
    "Executor",
    "PythonCoverageExecutor",
    "InProcessCoverageExecutor",
    "PersistentCoverageExecutor",
    "DifferentialExecutor",
    "RawProcessExecutor",
    "RawArc",
    "RawCoverageFile",
    "RawCoverageMap",
    "DiffKind",
    "ExecutorResult",
]

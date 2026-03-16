"""Package providing differential execution helpers.

Not meant to be used directly by the fuzzing engine; the engine will wrap the
appropriate executors based on configuration.
"""

from .differential import DifferentialExecutor
from .raw import RawProcessExecutor

__all__ = [
    "RawProcessExecutor",
    "DifferentialExecutor",
]

"""Differential executor scaffolding.

The concrete differential strategy will evolve over time; this package provides
the basic composition primitive for running blackbox and whitebox executors
together for the same input.
"""

from .composed import DifferentialExecutor, DifferentialResult

__all__ = [
    "DifferentialExecutor",
    "DifferentialResult",
]

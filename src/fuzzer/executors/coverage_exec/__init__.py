"""Coverage-specific executor implementations.

This subpackage contains runtime coverage execution support.
The persistent executor is the primary production path.
"""

from .persistent import PersistentCoverageExecutor

__all__ = [
    "PersistentCoverageExecutor",
]

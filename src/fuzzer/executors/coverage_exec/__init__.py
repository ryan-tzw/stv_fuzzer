"""Coverage-specific executor implementations.

This subpackage contains everything required to run a harness under
coverage.py: helper routines, the three executor classes, and a small
command-line shim used for manual experimentation.  The names inside this
package do **not** include the word "coverage" since the package itself
already provides that context.
"""

from .cli import main as coverage_cli_main
from .executors import (
    InProcessCoverageExecutor,
    PersistentCoverageExecutor,
    PythonCoverageExecutor,
)

__all__ = [
    "PythonCoverageExecutor",
    "InProcessCoverageExecutor",
    "PersistentCoverageExecutor",
    "coverage_cli_main",
]

"""
Base executor interface and utilities.

An ``Executor`` is responsible for driving a single fuzz target execution.  It
may be as simple as invoking ``subprocess.run`` or as complex as maintaining a
long-lived worker process.  All executors expose the same minimal API so the
fuzzing engine can be agnostic about the underlying execution strategy.

The return type of :meth:`run` is intentionally loose (``Any``) because
different executors may produce different kinds of auxiliary data: coverage
information, file paths, differential flags, etc.
"""

from abc import ABC, abstractmethod
from typing import Any, Tuple


class Executor(ABC):
    """Abstract base class for fuzzing executors.

    The engine expects ``run`` to return a three-element tuple ``(stdout,
    stderr, result)``.  ``result`` may be a coverage dictionary, a file path, a
    boolean diff indicator, or anything else that makes sense for the
    concrete executor.

    Executors that need to perform setup/teardown (persistent workers,
    networked proxies, etc.) may override :meth:`start` and :meth:`stop`.
    """

    @abstractmethod
    def run(self, input_data: str | None = None) -> Tuple[str, str, Any]:
        """Execute the target with *input_data* and return ``(stdout, stderr,
        result)``.
        """
        ...

    # ``start``/``stop`` are optional hooks; the default implementations are
    # no-ops so that lightweight executors need not deal with them.
    def start(self) -> None:  # pragma: no cover - trivial
        """Prepare the executor for use (called before fuzzing begins)."""
        pass

    def stop(self) -> None:  # pragma: no cover - trivial
        """Clean up any resources acquired by :meth:`start`."""
        pass

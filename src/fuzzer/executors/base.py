"""
Base executor interface.

Executors run a fuzz target and return an :class:`ExecutorResult`.
``start``/``stop`` are optional hooks for persistent implementations.
"""

from abc import ABC, abstractmethod

from fuzzer.executors.executor_types import ExecutorResult


class Executor(ABC):
    """Abstract base class for fuzzing executors.

    The engine expects ``run`` to return an :class:`ExecutorResult`.

    Executors that need to perform setup/teardown (persistent workers,
    networked proxies, etc.) may override :meth:`start` and :meth:`stop`.
    """

    @abstractmethod
    def run(self, input_data: str | None = None) -> ExecutorResult:
        """Execute the target with *input_data* and return an ExecutorResult."""
        ...

    # ``start``/``stop`` are optional hooks; the default implementations are
    # no-ops so that lightweight executors need not deal with them.
    def start(self) -> None:  # pragma: no cover - trivial
        """Prepare the executor for use (called before fuzzing begins)."""
        pass

    def stop(self) -> None:  # pragma: no cover - trivial
        """Clean up any resources acquired by :meth:`start`."""
        pass

"""
Base executor interface.

Executors run a fuzz target and return :class:`ExecutionResult`; ``result`` is
generic (coverage, path, diff, etc.). ``start``/``stop`` are optional hooks
for persistent implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

_ResultT = TypeVar("_ResultT")


@dataclass(frozen=True)
class ExecutionResult(Generic[_ResultT]):
    """Result of one executor invocation."""

    stdout: str
    stderr: str
    exit_code: int
    result: _ResultT


class Executor(ABC):
    """Abstract base class for fuzzing executors.

    The engine expects ``run`` to return :class:`ExecutionResult`. ``result``
    may be a coverage dictionary, a file path, a boolean diff indicator, or
    anything else that makes sense for the concrete executor.

    Executors that need to perform setup/teardown (persistent workers,
    networked proxies, etc.) may override :meth:`start` and :meth:`stop`.
    """

    @abstractmethod
    def run(self, input_data: str | None = None) -> ExecutionResult[Any]:
        """Execute the target with *input_data* and return an ExecutionResult."""
        ...

    # ``start``/``stop`` are optional hooks; the default implementations are
    # no-ops so that lightweight executors need not deal with them.
    def start(self) -> None:  # pragma: no cover - trivial
        """Prepare the executor for use (called before fuzzing begins)."""
        pass

    def stop(self) -> None:  # pragma: no cover - trivial
        """Clean up any resources acquired by :meth:`start`."""
        pass

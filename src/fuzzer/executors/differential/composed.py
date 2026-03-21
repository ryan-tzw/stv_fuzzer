"""Composed differential executor scaffold.

This class runs two executors for the same input:
- blackbox target executor (authoritative stdout/stderr/exit_code)
- whitebox reference executor (proxy analysis signal, e.g. coverage)
"""

from dataclasses import dataclass
from typing import Any

from fuzzer.executors.base import ExecutionResult, Executor


@dataclass(frozen=True)
class DifferentialResult:
    """Container for raw blackbox and whitebox execution results."""

    blackbox: ExecutionResult[Any]
    whitebox: ExecutionResult[Any]


class DifferentialExecutor(Executor):
    """Execute blackbox and whitebox executors for the same fuzz input.

    Notes
    -----
    This is intentionally a scaffold. It does not perform any comparison or
    interest classification yet; it only composes and returns both execution
    results so later stages can build differential logic on top.
    """

    def __init__(self, blackbox: Executor, whitebox: Executor) -> None:
        self.blackbox = blackbox
        self.whitebox = whitebox

    def start(self) -> None:
        self.blackbox.start()
        self.whitebox.start()

    def stop(self) -> None:
        self.blackbox.stop()
        self.whitebox.stop()

    def run(self, input_data: str | None = None) -> ExecutionResult[DifferentialResult]:
        """Run both executors and return a bundled result.

        The top-level stdout/stderr/exit_code are taken from the blackbox run,
        because that is the system under test from the fuzzer's perspective.
        """
        blackbox_result = self.blackbox.run(input_data)
        whitebox_result = self.whitebox.run(input_data)

        return ExecutionResult(
            stdout=blackbox_result.stdout,
            stderr=blackbox_result.stderr,
            exit_code=blackbox_result.exit_code,
            result=DifferentialResult(
                blackbox=blackbox_result,
                whitebox=whitebox_result,
            ),
        )

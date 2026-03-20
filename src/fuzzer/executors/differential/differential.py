"""Differential executor that compares a blackbox run with a reference."""

from typing import List, Protocol

from fuzzer.executors.executor_types import ExecutorResult

from .raw import RawProcessExecutor


class _ReferenceExecutor(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def run(self, input_data: str | None = None) -> ExecutorResult: ...


class DifferentialExecutor:
    """Run both a blackbox command and a reference executor side-by-side.

    *black_cmd* is executed with :class:`RawProcessExecutor`.
    *ref_executor* should be an executor returning :class:`ExecutorResult`
    (e.g. a coverage executor).

    Differential decisions are outcome-based only:
    success (return_code == 0) versus failure (return_code != 0).
    Raw stdout/stderr are still preserved in the returned result for debugging.
    """

    def __init__(
        self,
        black_cmd: List[str],
        ref_executor: _ReferenceExecutor,
    ) -> None:
        self.black = RawProcessExecutor(black_cmd)
        self.ref = ref_executor

    def start(self) -> None:
        self.black.start()
        self.ref.start()

    def stop(self) -> None:
        self.black.stop()
        self.ref.stop()

    def run(self, input_data: str | None = None) -> ExecutorResult:
        black = self.black.run(input_data)
        ref = self.ref.run(input_data)

        diff_kind = None
        if black.diff_kind == "executor_failure" or ref.diff_kind == "executor_failure":
            diff_kind = "executor_failure"
        else:
            black_ok = black.return_code == 0
            ref_ok = ref.return_code == 0
            if black_ok != ref_ok:
                diff_kind = "outcome_mismatch"

        return ExecutorResult(
            stdout=black.stdout,
            stderr=black.stderr,
            return_code=black.return_code,
            raw_coverage=ref.raw_coverage,
            is_diff=diff_kind is not None,
            diff_kind=diff_kind,
        )

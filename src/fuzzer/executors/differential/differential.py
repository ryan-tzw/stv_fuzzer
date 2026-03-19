"""Differential executor that compares a blackbox run with a reference."""

from typing import List, Protocol

from fuzzer.executors.executor_types import ExecutorResult

from .raw import RawProcessExecutor


class _ReferenceExecutor(Protocol):
    def run(self, input_data: str | None = None) -> ExecutorResult: ...


class DifferentialExecutor:
    """Run both a blackbox command and a reference executor side-by-side.

    *black_cmd* is executed with :class:`RawProcessExecutor`.
    *ref_executor* should be an executor returning :class:`ExecutorResult`
    (e.g. a coverage executor).
    """

    def __init__(
        self,
        black_cmd: List[str],
        ref_executor: _ReferenceExecutor,
    ) -> None:
        self.black = RawProcessExecutor(black_cmd)
        self.ref = ref_executor

    def run(self, input_data: str | None = None) -> ExecutorResult:
        black = self.black.run(input_data)
        ref = self.ref.run(input_data)

        diff_kind = None
        if black.stdout != ref.stdout:
            diff_kind = "stdout_mismatch"
        elif black.stderr != ref.stderr:
            diff_kind = "stderr_mismatch"
        elif black.return_code != ref.return_code:
            diff_kind = "return_code_mismatch"
        elif black.return_code != 0:
            diff_kind = "blackbox_nonzero"
        elif ref.return_code != 0:
            diff_kind = "reference_nonzero"

        return ExecutorResult(
            stdout=black.stdout,
            stderr=black.stderr,
            return_code=black.return_code,
            raw_coverage=ref.raw_coverage,
            is_diff=diff_kind is not None,
            diff_kind=diff_kind,
        )

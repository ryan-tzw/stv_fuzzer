"""Differential executor that compares a blackbox run with a reference."""

from typing import Any, List, Tuple

from .raw import RawProcessExecutor


class DifferentialExecutor:
    """Run both a blackbox command and a reference executor side-by-side.

    *black_cmd* is executed with :class:`RawProcessExecutor`.
    *ref_executor* should be an executor returning ``(stdout, stderr, coverage)``
    (e.g. a coverage executor).

    ``run`` returns a tuple ``(stdout, stderr, coverage, diff)`` where *diff*
    is ``True`` if either output differs or the blackbox exit code was nonzero.
    """

    def __init__(
        self,
        black_cmd: List[str],
        ref_executor: Any,
    ) -> None:
        self.black = RawProcessExecutor(black_cmd)
        self.ref = ref_executor

    def run(self, input_data: str | None = None) -> Tuple[str, str, Any, bool]:
        stdout_b, stderr_b, code_b = self.black.run(input_data)
        stdout_r, stderr_r, cov = self.ref.run(input_data)
        diff = (stdout_b != stdout_r) or (stderr_b != stderr_r) or (code_b != 0)
        return stdout_b, stderr_b, cov, diff

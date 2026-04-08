"""Feedback policy for differential fuzzing signals."""

from fuzzer.feedback.coverage import CoverageFeedback
from fuzzer.observers.differential import DifferentialSignal


class DifferentialFeedback:
    """Evaluate DifferentialSignal and decide corpus interestingness.

    The policy is intentionally simple and configurable. By default it treats
    new whitebox coverage, blackbox non-zero exits, blackbox traceback output,
    and exit-code mismatches as interesting.
    """

    def __init__(
        self,
        *,
        use_whitebox_coverage: bool = True,
        use_blackbox_nonzero_exit: bool = True,
        use_blackbox_traceback: bool = True,
        use_exit_code_mismatch: bool = True,
        use_blackbox_stderr: bool = False,
        use_whitebox_nonzero_exit: bool = False,
    ) -> None:
        self._coverage_feedback = CoverageFeedback()
        self.use_whitebox_coverage = use_whitebox_coverage
        self.use_blackbox_nonzero_exit = use_blackbox_nonzero_exit
        self.use_blackbox_traceback = use_blackbox_traceback
        self.use_exit_code_mismatch = use_exit_code_mismatch
        self.use_blackbox_stderr = use_blackbox_stderr
        self.use_whitebox_nonzero_exit = use_whitebox_nonzero_exit

    def evaluate(self, signal: DifferentialSignal) -> bool:
        """Return True when signal should be considered interesting."""
        if self.use_whitebox_coverage and self._coverage_feedback.evaluate(
            signal.whitebox_coverage
        ):
            return True

        if self.use_blackbox_nonzero_exit and signal.blackbox_nonzero_exit:
            return True

        if self.use_blackbox_traceback and signal.blackbox_has_traceback:
            return True

        if self.use_exit_code_mismatch and signal.exit_code_mismatch:
            return True

        if self.use_blackbox_stderr and signal.blackbox_has_stderr:
            return True

        if self.use_whitebox_nonzero_exit and signal.whitebox_nonzero_exit:
            return True

        return False

    def on_cycle_start(self, cycle: int) -> None:
        """Forward cycle boundary notification to internal coverage feedback."""
        self._coverage_feedback.on_cycle_start(cycle)

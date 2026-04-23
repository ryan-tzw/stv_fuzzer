"""Feedback policy for differential fuzzing signals."""

from fuzzer.feedback.coverage import CoverageFeedback
from fuzzer.observers.bug_category import is_non_actionable_runner_crash
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

        non_actionable = is_non_actionable_runner_crash(signal.parsed_crash)
        if non_actionable:
            if self.use_whitebox_nonzero_exit and signal.whitebox_nonzero_exit:
                return True
            return False

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

    @property
    def total_seen_lines(self) -> int:
        """Expose cumulative unique lines seen by whitebox coverage feedback."""
        return self._coverage_feedback.total_seen_lines

    @property
    def total_seen_branches(self) -> int:
        """Expose cumulative unique branches seen by whitebox coverage feedback."""
        return self._coverage_feedback.total_seen_branches

    @property
    def total_seen_arcs(self) -> int:
        """Expose cumulative unique arcs seen by whitebox coverage feedback."""
        return self._coverage_feedback.total_seen_arcs

    @property
    def seen_lines(self) -> frozenset[tuple[str, int]]:
        """Expose unique covered lines seen by whitebox coverage feedback."""
        return self._coverage_feedback.seen_lines

    @property
    def seen_branches(self) -> frozenset[tuple[str, tuple[int, int]]]:
        """Expose unique covered branch exits seen by whitebox coverage feedback."""
        return self._coverage_feedback.seen_branches

    @property
    def seen_arcs(self) -> frozenset[tuple[str, tuple[int, int]]]:
        """Expose unique covered arcs seen by whitebox coverage feedback."""
        return self._coverage_feedback.seen_arcs

"""
Coverage feedback: takes normalised coverage signals from the observer
and decides whether an input should be added to the corpus or recorded
as a crash.
"""

from dataclasses import dataclass

from fuzzer.observers.python_coverage import CoverageData


@dataclass
class FeedbackResult:
    """Decision produced by CoverageFeedback for a single execution."""

    add_to_corpus: bool
    is_crash: bool


class CoverageFeedback:
    """
    Stateful feedback handler for coverage-guided fuzzing.

    Responsibilities:
    - Track which lines/branches have been seen globally.
    - Given a CoverageData signal and raw stderr, decide whether the
      input is interesting (new coverage) and/or a crash.
    """

    def __init__(self) -> None:
        self._seen_lines: set[tuple[str, int]] = set()
        self._seen_branches: set[tuple[str, tuple[int, int]]] = set()

    def evaluate(self, signal: CoverageData, stderr: str = "") -> FeedbackResult:
        """
        Evaluate an execution's signals and return a decision.

        Args:
            signal:  Normalised coverage data produced by the observer.
            stderr:  Raw stderr output from the executor (used for crash detection).

        Returns:
            FeedbackResult indicating whether to add to corpus and/or record a crash.
        """
        is_crash = "ERR:" in stderr

        is_new_coverage = self._has_new_coverage(signal)
        if is_new_coverage:
            self._update_seen(signal)

        return FeedbackResult(
            add_to_corpus=is_new_coverage,
            is_crash=is_crash,
        )

    def _has_new_coverage(self, signal: CoverageData) -> bool:
        """Return True if signal contains any lines or branches not seen before."""
        for file, lines in signal.lines.items():
            for line in lines:
                if (file, line) not in self._seen_lines:
                    return True
        for file, branches in signal.branches.items():
            for branch in branches:
                if (file, branch) not in self._seen_branches:
                    return True
        return False

    def _update_seen(self, signal: CoverageData) -> None:
        """Absorb all coverage in signal into the global seen sets."""
        for file, lines in signal.lines.items():
            for line in lines:
                self._seen_lines.add((file, line))
        for file, branches in signal.branches.items():
            for branch in branches:
                self._seen_branches.add((file, branch))

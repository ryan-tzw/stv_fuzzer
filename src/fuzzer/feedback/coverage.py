"""
Coverage feedback: takes normalised coverage signals from the observer
and decides whether an input should be added to the corpus.
"""

from fuzzer.observers.python_coverage import CoverageData


class CoverageFeedback:
    """
    Stateful feedback handler for coverage-guided fuzzing.

    Responsibilities:
    - Track which lines/arcs have been seen globally.
    - Given a CoverageData signal, decide whether the input is interesting.
      Interestingness is arc-based: only new arcs add inputs to corpus.
    """

    def __init__(self) -> None:
        self._seen_lines: set[tuple[str, int]] = set()
        self._seen_branches: set[tuple[str, tuple[int, int]]] = set()

    def evaluate(self, signal: CoverageData) -> bool:
        """
        Evaluate coverage and return whether this input should enter the corpus.

        Args:
            signal:  Normalised coverage data produced by the observer.

        Returns:
            True if this execution contributes at least one new arc, False otherwise.
        """
        is_new_arc = self._has_new_arc(signal)
        if is_new_arc:
            self._update_seen(signal)
        return is_new_arc

    def _has_new_arc(self, signal: CoverageData) -> bool:
        """Return True if signal contains any arcs not seen before."""
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

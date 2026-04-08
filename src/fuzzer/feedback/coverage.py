"""
Coverage feedback: takes normalised coverage signals from the observer
and decides whether an input should be added to the corpus.
"""

from collections import deque

from fuzzer.feedback.rare_arc import ArcKey, RareArcFallback
from fuzzer.observers.python_coverage import CoverageData


class CoverageFeedback:
    """
    Stateful feedback handler for coverage-guided fuzzing.

    Interestingness is primarily arc novelty, with a conservative rare-arc
    fallback for no-new-arc candidates.
    """

    def __init__(self) -> None:
        self._rare_arc = RareArcFallback()

        self._seen_lines: set[tuple[str, int]] = set()
        self._seen_arcs: set[ArcKey] = set()
        self._seen_branches: set[ArcKey] = set()

        self._arc_doc_freq: dict[ArcKey, int] = {}
        self._corpus_docs = 0
        self._fallback_scores: deque[float] = deque(maxlen=256)
        self._current_cycle: int | None = None
        self._fallback_accepts_this_cycle = 0

    def evaluate(self, signal: CoverageData) -> bool:
        """
        Evaluate coverage and return whether this input should enter the corpus.

        Returns:
            True if this execution contributes either:
            - at least one new arc, or
            - a fallback-accepted rare-arc profile.
        """
        candidate_arcs = self._candidate_arcs(signal)
        if self._try_accept_new_arc(signal, candidate_arcs):
            return True

        if self._try_accept_fallback(signal, candidate_arcs):
            return True

        return False

    def on_cycle_start(self, cycle: int) -> None:
        """Reset per-cycle fallback acceptance quota when cycle changes."""
        if self._current_cycle == cycle:
            return
        self._current_cycle = cycle
        self._fallback_accepts_this_cycle = 0

    @staticmethod
    def _candidate_arcs(signal: CoverageData) -> set[ArcKey]:
        arcs: set[ArcKey] = set()
        for file, branches in signal.branches.items():
            for branch in branches:
                arcs.add((file, branch))
        return arcs

    def _has_new_arc(self, candidate_arcs: set[ArcKey]) -> bool:
        """Return True if candidate contains any arcs not seen before."""
        return any(arc not in self._seen_arcs for arc in candidate_arcs)

    def _try_accept_new_arc(
        self, signal: CoverageData, candidate_arcs: set[ArcKey]
    ) -> bool:
        if not self._has_new_arc(candidate_arcs):
            return False
        self._accept_candidate(signal, candidate_arcs)
        return True

    def _try_accept_fallback(
        self, signal: CoverageData, candidate_arcs: set[ArcKey]
    ) -> bool:
        fallback_score = self._rare_arc.score(
            candidate_arcs, docs=self._corpus_docs, arc_doc_freq=self._arc_doc_freq
        )
        accept_fallback = self._rare_arc.should_accept(
            candidate_arcs,
            fallback_score=fallback_score,
            docs=self._corpus_docs,
            arc_doc_freq=self._arc_doc_freq,
            recent_scores=self._fallback_scores,
            fallback_accepts_this_cycle=self._fallback_accepts_this_cycle,
        )
        self._fallback_scores.append(fallback_score)
        if not accept_fallback:
            return False
        self._accept_candidate(signal, candidate_arcs, via_fallback=True)
        return True

    def _accept_candidate(
        self,
        signal: CoverageData,
        candidate_arcs: set[ArcKey],
        *,
        via_fallback: bool = False,
    ) -> None:
        self._update_seen(signal)
        self._record_accepted_candidate(candidate_arcs)
        if via_fallback:
            self._fallback_accepts_this_cycle += 1

    def _update_seen(self, signal: CoverageData) -> None:
        """Absorb all coverage in signal into the global seen sets."""
        for file, lines in signal.lines.items():
            for line in lines:
                self._seen_lines.add((file, line))

        decision_lines_by_file = signal.branch_decision_lines
        for file, branches in signal.branches.items():
            decision_lines = decision_lines_by_file.get(file, frozenset())
            for branch in branches:
                arc = (file, branch)
                self._seen_arcs.add(arc)
                if branch[0] in decision_lines:
                    self._seen_branches.add(arc)

    def _record_accepted_candidate(self, candidate_arcs: set[ArcKey]) -> None:
        """Record one accepted input's arc presence into corpus-level frequencies."""
        self._corpus_docs += 1
        for arc in candidate_arcs:
            self._arc_doc_freq[arc] = self._arc_doc_freq.get(arc, 0) + 1

    @property
    def total_seen_lines(self) -> int:
        """Return total unique covered lines observed globally."""
        return len(self._seen_lines)

    @property
    def total_seen_branches(self) -> int:
        """Return total unique covered branches observed globally."""
        return len(self._seen_branches)

    @property
    def total_seen_arcs(self) -> int:
        """Return total unique covered arcs observed globally."""
        return len(self._seen_arcs)

"""
Coverage feedback: takes normalised coverage signals from the observer
and decides whether an input should be added to the corpus.
"""

from collections import deque

from fuzzer.feedback.coverage_state import CoverageState
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
        self._state = CoverageState()
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
        return self._state.has_new_arc(candidate_arcs)

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
            candidate_arcs,
            docs=self._state.corpus_docs,
            arc_doc_freq=self._state.arc_doc_freq,
        )
        accept_fallback = self._rare_arc.should_accept(
            candidate_arcs,
            fallback_score=fallback_score,
            docs=self._state.corpus_docs,
            arc_doc_freq=self._state.arc_doc_freq,
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
        self._state.update_seen(signal)
        self._state.record_accepted_candidate(candidate_arcs)
        if via_fallback:
            self._fallback_accepts_this_cycle += 1

    @property
    def total_seen_lines(self) -> int:
        """Return total unique covered lines observed globally."""
        return self._state.total_seen_lines

    @property
    def total_seen_branches(self) -> int:
        """Return total unique covered branches observed globally."""
        return self._state.total_seen_branches

    @property
    def total_seen_arcs(self) -> int:
        """Return total unique covered arcs observed globally."""
        return self._state.total_seen_arcs

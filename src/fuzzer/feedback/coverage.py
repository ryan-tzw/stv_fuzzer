"""
Coverage feedback: takes normalised coverage signals from the observer
and decides whether an input should be added to the corpus.
"""

import math
from collections import deque

from fuzzer.observers.python_coverage import CoverageData

ArcKey = tuple[str, tuple[int, int]]


class CoverageFeedback:
    """
    Stateful feedback handler for coverage-guided fuzzing.

    Interestingness is primarily arc novelty, with a conservative rare-arc
    fallback for no-new-arc candidates.
    """

    def __init__(self) -> None:
        self._top_k = 8
        self._warmup_docs = 32
        self._min_candidate_arcs = 4
        self._min_rare_hits = 2
        self._rare_fraction = 0.05
        self._fallback_percentile = 95.0
        self._max_fallback_accepts_per_cycle = 1

        self._seen_lines: set[tuple[str, int]] = set()
        self._seen_arcs: set[ArcKey] = set()

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
        if self._has_new_arc(candidate_arcs):
            self._update_seen(signal)
            self._record_accepted_candidate(candidate_arcs)
            return True

        fallback_score = self._fallback_score(candidate_arcs)
        accept_fallback = self._should_accept_fallback(candidate_arcs, fallback_score)
        self._fallback_scores.append(fallback_score)
        if accept_fallback:
            self._update_seen(signal)
            self._record_accepted_candidate(candidate_arcs)
            self._fallback_accepts_this_cycle += 1
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

    def _fallback_score(self, candidate_arcs: set[ArcKey]) -> float:
        if not candidate_arcs:
            return 0.0

        docs = self._corpus_docs
        weights = [
            math.log((docs + 1.0) / (self._arc_doc_freq.get(arc, 0) + 1.0))
            for arc in candidate_arcs
        ]
        top_weights = sorted(weights, reverse=True)[: self._top_k]
        return sum(top_weights) / math.sqrt(len(candidate_arcs))

    def _should_accept_fallback(
        self, candidate_arcs: set[ArcKey], fallback_score: float
    ) -> bool:
        docs = self._corpus_docs
        if docs < self._warmup_docs:
            return False
        if len(candidate_arcs) < self._min_candidate_arcs:
            return False
        if self._fallback_accepts_this_cycle >= self._max_fallback_accepts_per_cycle:
            return False

        rare_cutoff = max(2, int(math.floor(self._rare_fraction * docs)))
        rare_hits = sum(
            1 for arc in candidate_arcs if self._arc_doc_freq.get(arc, 0) <= rare_cutoff
        )
        if rare_hits < self._min_rare_hits:
            return False

        threshold = self._percentile(self._fallback_scores, self._fallback_percentile)
        return fallback_score >= threshold

    @staticmethod
    def _percentile(values: deque[float], percentile: float) -> float:
        if not values:
            return float("inf")
        sorted_vals = sorted(values)
        rank = int(math.ceil((percentile / 100.0) * len(sorted_vals))) - 1
        rank = max(0, min(rank, len(sorted_vals) - 1))
        return sorted_vals[rank]

    def _update_seen(self, signal: CoverageData) -> None:
        """Absorb all coverage in signal into the global seen sets."""
        for file, lines in signal.lines.items():
            for line in lines:
                self._seen_lines.add((file, line))
        for file, branches in signal.branches.items():
            for branch in branches:
                self._seen_arcs.add((file, branch))

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
        return len(self._seen_arcs)

    @property
    def total_seen_arcs(self) -> int:
        """Return total unique covered arcs observed globally."""
        return len(self._seen_arcs)

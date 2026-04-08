"""Rare-arc fallback scoring and gating helpers."""

import math
from collections import deque
from dataclasses import dataclass

ArcKey = tuple[str, tuple[int, int]]


@dataclass(frozen=True)
class RareArcFallbackPolicy:
    top_k: int = 8
    warmup_docs: int = 32
    min_candidate_arcs: int = 4
    min_rare_hits: int = 2
    rare_fraction: float = 0.05
    fallback_percentile: float = 95.0
    max_fallback_accepts_per_cycle: int = 1


class RareArcFallback:
    """Pure scoring/gating logic for no-new-arc fallback decisions."""

    def __init__(self, policy: RareArcFallbackPolicy | None = None) -> None:
        self._policy = policy or RareArcFallbackPolicy()

    def score(
        self, candidate_arcs: set[ArcKey], *, docs: int, arc_doc_freq: dict[ArcKey, int]
    ) -> float:
        if not candidate_arcs:
            return 0.0

        weights = [
            math.log((docs + 1.0) / (arc_doc_freq.get(arc, 0) + 1.0))
            for arc in candidate_arcs
        ]
        top_weights = sorted(weights, reverse=True)[: self._policy.top_k]
        return sum(top_weights) / math.sqrt(len(candidate_arcs))

    def should_accept(
        self,
        candidate_arcs: set[ArcKey],
        *,
        fallback_score: float,
        docs: int,
        arc_doc_freq: dict[ArcKey, int],
        recent_scores: deque[float],
        fallback_accepts_this_cycle: int,
    ) -> bool:
        if not self._passes_prerequisites(
            candidate_arcs,
            docs=docs,
            fallback_accepts_this_cycle=fallback_accepts_this_cycle,
        ):
            return False

        if (
            self._rare_hits(candidate_arcs, docs=docs, arc_doc_freq=arc_doc_freq)
            < self._policy.min_rare_hits
        ):
            return False

        threshold = self._score_threshold(recent_scores)
        return fallback_score >= threshold

    def _passes_prerequisites(
        self,
        candidate_arcs: set[ArcKey],
        *,
        docs: int,
        fallback_accepts_this_cycle: int,
    ) -> bool:
        if docs < self._policy.warmup_docs:
            return False
        if len(candidate_arcs) < self._policy.min_candidate_arcs:
            return False
        if fallback_accepts_this_cycle >= self._policy.max_fallback_accepts_per_cycle:
            return False
        return True

    def _rare_cutoff(self, docs: int) -> int:
        return max(2, int(math.floor(self._policy.rare_fraction * docs)))

    def _rare_hits(
        self, candidate_arcs: set[ArcKey], *, docs: int, arc_doc_freq: dict[ArcKey, int]
    ) -> int:
        rare_cutoff = self._rare_cutoff(docs)
        return sum(
            1 for arc in candidate_arcs if arc_doc_freq.get(arc, 0) <= rare_cutoff
        )

    def _score_threshold(self, recent_scores: deque[float]) -> float:
        return self._percentile(recent_scores, self._policy.fallback_percentile)

    @staticmethod
    def _percentile(values: deque[float], percentile: float) -> float:
        if not values:
            return float("inf")
        sorted_vals = sorted(values)
        rank = int(math.ceil((percentile / 100.0) * len(sorted_vals))) - 1
        rank = max(0, min(rank, len(sorted_vals) - 1))
        return sorted_vals[rank]

"""Coverage state bookkeeping for coverage-guided feedback."""

from fuzzer.feedback.rare_arc import ArcKey
from fuzzer.observers.python_coverage import CoverageData


class CoverageState:
    """Mutable storage for seen coverage and corpus-level arc frequencies."""

    def __init__(self) -> None:
        self._seen_lines: set[tuple[str, int]] = set()
        self._seen_arcs: set[ArcKey] = set()
        self._seen_branches: set[ArcKey] = set()
        self._arc_doc_freq: dict[ArcKey, int] = {}
        self._corpus_docs = 0

    def has_new_arc(self, candidate_arcs: set[ArcKey]) -> bool:
        return any(arc not in self._seen_arcs for arc in candidate_arcs)

    def update_seen(self, signal: CoverageData) -> None:
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

    def record_accepted_candidate(self, candidate_arcs: set[ArcKey]) -> None:
        self._corpus_docs += 1
        for arc in candidate_arcs:
            self._arc_doc_freq[arc] = self._arc_doc_freq.get(arc, 0) + 1

    @property
    def corpus_docs(self) -> int:
        return self._corpus_docs

    @property
    def arc_doc_freq(self) -> dict[ArcKey, int]:
        return self._arc_doc_freq

    @property
    def total_seen_lines(self) -> int:
        return len(self._seen_lines)

    @property
    def total_seen_branches(self) -> int:
        return len(self._seen_branches)

    @property
    def total_seen_arcs(self) -> int:
        return len(self._seen_arcs)

    @property
    def seen_lines(self) -> frozenset[tuple[str, int]]:
        return frozenset(self._seen_lines)

    @property
    def seen_branches(self) -> frozenset[ArcKey]:
        return frozenset(self._seen_branches)

    @property
    def seen_arcs(self) -> frozenset[ArcKey]:
        return frozenset(self._seen_arcs)

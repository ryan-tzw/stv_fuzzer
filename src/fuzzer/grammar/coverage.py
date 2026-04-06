"""Grammar coverage tracking to guide mutations toward under-explored parts."""

from collections import defaultdict
from typing import Dict

from fuzzer.grammar.tree import Node


class GrammarCoverage:
    """Tracks how often each grammar symbol has been exercised."""

    def __init__(self):
        self.symbol_counts: Dict[str, int] = defaultdict(int)
        self.total_inputs: int = 0

    def update_from_tree(self, tree: Node) -> None:
        """Update coverage from a successfully parsed tree."""
        self._walk_and_count(tree)
        self.total_inputs += 1

    def _walk_and_count(self, node: Node) -> None:
        """Recursively count every symbol in the tree."""
        self.symbol_counts[node.symbol] += 1
        for child in node.children:
            self._walk_and_count(child)

    def get_symbol_weight(self, symbol: str) -> float:
        """Higher weight = rarer symbol = more interesting to mutate.
        Uses simple inverse-frequency with smoothing."""
        count = self.symbol_counts[symbol]
        return 1.0 / (count + 1.0)  # never-seen symbols get weight ~1.0

    def __repr__(self) -> str:
        if not self.symbol_counts:
            return "GrammarCoverage(<empty>)"
        top = sorted(self.symbol_counts.items(), key=lambda x: x[1])[:8]
        return f"GrammarCoverage({self.total_inputs} inputs, top-under-covered: {top})"

"""Fragment extraction and pooling for internal grammar Node trees."""

import random

from dataclasses import dataclass, field

from fuzzer.grammar.tree import Node
from fuzzer.grammar.coverage import GrammarCoverage

MAX_FRAGMENTS_PER_SYMBOL: int = 200


def _clone_node(node: Node) -> Node:
    """Deep-copy a Node subtree."""
    return Node(
        symbol=node.symbol,
        children=[_clone_node(child) for child in node.children],
        text=node.text,
    )


@dataclass
class FragmentPool:
    """Store reusable subtree fragments grouped by symbol."""

    fragments_by_symbol: dict[str, list[Node]] = field(default_factory=dict)

    def add(self, node: Node) -> None:
        bucket = self.fragments_by_symbol.setdefault(node.symbol, [])
        if len(bucket) < MAX_FRAGMENTS_PER_SYMBOL:
            clone = _clone_node(node)
            bucket.append(clone)

    def add_tree(self, root: Node) -> None:
        self.add(root)
        for child in root.children:
            self.add_tree(child)

    def get(self, symbol: str) -> list[Node]:
        fragments = self.fragments_by_symbol.get(symbol, [])
        return [_clone_node(node) for node in fragments]

    def symbols(self) -> tuple[str, ...]:
        return tuple(sorted(self.fragments_by_symbol.keys()))

    def count(self, symbol: str) -> int:
        return len(self.fragments_by_symbol.get(symbol, []))

    def get_weighted(
        self, symbol: str, coverage: GrammarCoverage, rng: random.Random
    ) -> Node | None:
        """Return a fragment for the symbol, biased toward coverage guidance."""
        fragments = self.fragments_by_symbol.get(symbol, [])
        if not fragments:
            return None

        if len(fragments) == 1:
            return _clone_node(fragments[0])

        # Weight every fragment by how under-covered its symbol is
        weights = [coverage.get_symbol_weight(symbol) for _ in fragments]
        total = sum(weights)
        weights = [w / total for w in weights]

        chosen = rng.choices(fragments, weights=weights, k=1)[0]
        return _clone_node(chosen)

    def __repr__(self) -> str:
        parts = [f"{symbol}:{self.count(symbol)}" for symbol in self.symbols()]
        return f"FragmentPool({', '.join(parts)})"

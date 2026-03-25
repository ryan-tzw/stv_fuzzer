"""Fragment extraction and pooling for internal grammar Node trees."""

from dataclasses import dataclass, field

from fuzzer.grammar.tree import Node


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
        clone = _clone_node(node)
        self.fragments_by_symbol.setdefault(node.symbol, []).append(clone)

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

    def __repr__(self) -> str:
        parts = [f"{symbol}:{self.count(symbol)}" for symbol in self.symbols()]
        return f"FragmentPool({', '.join(parts)})"

"""Internal tree structures for grammar-based parsing and mutation."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Node:
    """One node in the fuzzer's internal grammar tree."""

    symbol: str
    children: list["Node"] = field(default_factory=list)
    text: str | None = None

    def is_leaf(self) -> bool:
        return not self.children

    def is_terminal(self) -> bool:
        return self.is_leaf() and self.text is not None


@dataclass(frozen=True)
class ParseResult:
    """Result of parsing one input string."""

    success: bool
    tree: Node | None
    errors: list[str] = field(default_factory=list)

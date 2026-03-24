from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .generator import GrammarGenerator
from .mutator import GrammarTreeMutator
from .spec import GrammarSpec
from .tree import DerivationNode


class GrammarService(ABC):
    def __init__(self, spec: GrammarSpec, max_depth: int = 5) -> None:
        self.spec = spec
        self._generator = GrammarGenerator(spec, max_depth=max_depth)
        self._mutator = GrammarTreeMutator(spec, self._generator)

    @abstractmethod
    def parse(self, raw: str) -> DerivationNode | None:
        """Return a derivation tree for *raw* or None if parsing fails."""

    def generate(self) -> DerivationNode:
        return self._generator.generate()

    def generate_symbol(self, symbol: str) -> DerivationNode:
        return self._generator.generate_symbol(symbol)

    def mutate(
        self,
        tree: DerivationNode,
        donor_trees: Sequence[DerivationNode] | None = None,
    ) -> DerivationNode:
        return self._mutator.mutate(tree, donor_trees)

    def serialize(self, tree: DerivationNode) -> str:
        pieces: list[str] = []
        self._append_text(tree, pieces)
        return "".join(pieces)

    def _append_text(self, node: DerivationNode, pieces: list[str]) -> None:
        if node.text is not None:
            pieces.append(node.text)
            return
        for child in node.children:
            self._append_text(child, pieces)

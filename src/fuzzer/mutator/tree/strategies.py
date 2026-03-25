"""Tree-domain mutation strategies."""

from fuzzer.mutator.base import MutationOperation, MutationStrategy
from fuzzer.mutator.tree.operations import GrammarSubtreeReplace


class GrammarSubtreeStrategy(MutationStrategy):
    """Apply one grammar-aware same-symbol subtree replacement mutation."""

    def __init__(self, grammar_name: str = "ipv4"):
        self.operation = GrammarSubtreeReplace(grammar_name=grammar_name)

    def select(self) -> list[MutationOperation]:
        return [self.operation]

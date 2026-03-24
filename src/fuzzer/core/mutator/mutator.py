"""
Mutator: applies a mutation strategy to produce a mutated input.
"""

import argparse
from dataclasses import dataclass
from typing import Sequence

from fuzzer.core.corpus import SeedInput
from fuzzer.grammar import DerivationNode, GrammarService
from .strategies import MutationStrategy, RandomSingleStrategy


@dataclass
class MutantCandidate:
    raw_data: str
    tree: DerivationNode | None = None


class Mutator:
    def __init__(
        self,
        strategy: MutationStrategy | None = None,
        grammar: GrammarService | None = None,
    ):
        self.strategy = strategy or RandomSingleStrategy()
        self.grammar = grammar

    def mutate(
        self, seed: SeedInput, corpus: Sequence[SeedInput] | None = None
    ) -> MutantCandidate:
        """
        Produce a mutated candidate from *seed*.

        If a grammar tree is available, mutate the derivation tree directly and
        serialise it back to text. Otherwise, fall back to the legacy character
        mutator and try to parse the result back into a tree for future rounds.
        """
        if self.grammar is not None and seed.tree is not None:
            donor_trees = [
                other.tree
                for other in (corpus or [])
                if other is not seed and other.tree is not None
            ]
            for _ in range(3):
                tree = self.grammar.mutate(seed.tree, donor_trees)
                raw_data = self.grammar.serialize(tree)
                if raw_data != seed.raw_data:
                    return MutantCandidate(raw_data=raw_data, tree=tree)
            return MutantCandidate(raw_data=raw_data, tree=tree)

        raw_data = seed.raw_data
        for operation in self.strategy.select():
            raw_data = operation.mutate(raw_data)

        tree = self.grammar.parse(raw_data) if self.grammar is not None else None
        return MutantCandidate(raw_data=raw_data, tree=tree)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the mutator on an input string")
    parser.add_argument("input", help="Input string to mutate")
    args = parser.parse_args()

    mutator = Mutator()
    result = mutator.mutate(SeedInput(raw_data=args.input))
    print(f"Original: {args.input}")
    print(f"Mutated:  {result.raw_data}")

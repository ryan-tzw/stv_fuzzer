"""
Mutator: applies a mutation strategy to produce a mutated input.
"""

import random

from fuzzer.mutator.base import BaseMutator, MutationOperation, MutationStrategy
from fuzzer.mutator.string.operations import (
    DeleteChar,
    DuplicateChar,
    InsertRandomChar,
    RandomiseChar,
)


class Mutator(BaseMutator):
    def __init__(self, strategy: MutationStrategy | None = None):
        if strategy is None:
            from fuzzer.mutator.strategies import build_strategy

            strategy = build_strategy("random_single", grammar_name="ipv4")
        self.strategy = strategy
        self._string_fallback_ops: tuple[MutationOperation, ...] = (
            RandomiseChar(),
            DeleteChar(),
            InsertRandomChar(),
            DuplicateChar(),
        )

    def mutate(self, data: str) -> str:
        """Apply the strategy's selected operations to the input and return the result."""
        original = data
        for operation in self.strategy.select():
            data = operation.mutate(data)
        if data != original:
            return data
        return self._mutate_as_string(original)

    def _mutate_as_string(self, data: str) -> str:
        operations = list(self._string_fallback_ops)
        random.shuffle(operations)
        for operation in operations:
            mutated = operation.mutate(data)
            if mutated != data:
                return mutated
        return data

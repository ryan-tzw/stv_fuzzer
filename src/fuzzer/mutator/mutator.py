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
        fallback_ops = self.strategy.get_fallback_operations()
        self._string_fallback_ops: list[MutationOperation] = (
            fallback_ops
            if fallback_ops
            else [
                RandomiseChar(),
                DeleteChar(),
                InsertRandomChar(),
                DuplicateChar(),
            ]
        )

    def mutate(self, data: str) -> tuple[str, list[MutationOperation]]:
        """Apply the strategy's selected operations to the input and return the result."""
        operations = self.strategy.select()
        original = data
        for operation in operations:
            data = operation.mutate(data)

        if data != original:
            return data, operations

        fallback_mutated, fallback_op = self._mutate_as_string(original)
        if fallback_mutated != original and fallback_op is not None:
            return fallback_mutated, [fallback_op]

        return original, []

    def update_weights(
        self, operations: list[MutationOperation], reward: float = 0.0
    ) -> None:
        """Delegate weight updates to the internal strategy."""
        if not operations:
            return
        self.strategy.apply_decay()
        per_op_reward = reward / len(operations)
        for op in operations:
            self.strategy.update_weight(op, per_op_reward)

    def _mutate_as_string(self, data: str) -> tuple[str, MutationOperation | None]:
        if not self._string_fallback_ops:
            return data, None
        operations = list(self._string_fallback_ops)
        random.shuffle(operations)
        for operation in operations:
            mutated = operation.mutate(data)
            if mutated != data:
                return mutated, operation
        return data, None

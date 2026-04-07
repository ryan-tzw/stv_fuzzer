"""
Mutator: applies a mutation strategy to produce a mutated input.
"""

from fuzzer.mutator.base import BaseMutator, MutationStrategy, MutationOperation


class Mutator(BaseMutator):
    def __init__(self, strategy: MutationStrategy | None = None):
        if strategy is None:
            from fuzzer.mutator.strategies import build_strategy

            strategy = build_strategy("random_single", grammar_name="ipv4")
        self.strategy = strategy

    def mutate(self, data: str) -> tuple[str, list[MutationOperation]]:
        """Apply the strategy's selected operations to the input and return the result."""
        operations = self.strategy.select()
        mutated = data
        for operation in operations:
            mutated = operation.mutate(mutated)
        return mutated, operations

    def update_weights(
        self, operations: list[MutationOperation], reward: float = 0.0
    ) -> None:
        """Delegate weight updates to the internal strategy."""
        for op in operations:
            self.strategy.update_weight(op, reward)

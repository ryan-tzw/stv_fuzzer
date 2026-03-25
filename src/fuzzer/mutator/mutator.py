"""
Mutator: applies a mutation strategy to produce a mutated input.
"""

from .strategies import MutationStrategy, RandomSingleStrategy


class Mutator:
    def __init__(self, strategy: MutationStrategy | None = None):
        self.strategy = strategy or RandomSingleStrategy()

    def mutate(self, data: str) -> str:
        """Apply the strategy's selected operations to the input and return the result."""
        for operation in self.strategy.select():
            data = operation.mutate(data)
        return data

"""
Mutator: applies a mutation strategy to produce a mutated input.
"""

import argparse

from .strategies import MutationStrategy, RandomSingleStrategy


class Mutator:
    def __init__(self, strategy: MutationStrategy | None = None):
        self.strategy = strategy or RandomSingleStrategy()

    def mutate(self, data: str) -> str:
        """Apply the strategy's selected operations to the input and return the result."""
        for operation in self.strategy.select():
            data = operation.mutate(data)
        return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the mutator on an input string")
    parser.add_argument("input", help="Input string to mutate")
    args = parser.parse_args()

    mutator = Mutator()
    result = mutator.mutate(args.input)
    print(f"Original: {args.input}")
    print(f"Mutated:  {result}")

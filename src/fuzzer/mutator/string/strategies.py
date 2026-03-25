"""
Mutation strategies that determine how operations are selected and applied.
"""

import random

from fuzzer.mutator.base import MutationOperation, MutationStrategy


class RandomSingleStrategy(MutationStrategy):
    """Pick one random operation from a provided operation set."""

    def __init__(self, operations: list[MutationOperation]):
        if not operations:
            raise ValueError("RandomSingleStrategy requires at least one operation")
        self.operations = operations

    def select(self) -> list[MutationOperation]:
        return [random.choice(self.operations)]

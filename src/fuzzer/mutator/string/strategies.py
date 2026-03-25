"""
Mutation strategies that determine how operations are selected and applied.
"""

import random

from .operations import (
    DeleteChar,
    DuplicateChar,
    InsertRandomChar,
    RandomiseChar,
)
from fuzzer.mutator.base import MutationOperation, MutationStrategy

ALL_OPERATIONS: list[type[MutationOperation]] = [
    RandomiseChar,
    DeleteChar,
    InsertRandomChar,
    DuplicateChar,
]


class RandomSingleStrategy(MutationStrategy):
    """Pick one random operation from all available operations."""

    def __init__(self, operations: list[type[MutationOperation]] = ALL_OPERATIONS):
        self.operations = operations

    def select(self) -> list[MutationOperation]:
        return [random.choice(self.operations)()]

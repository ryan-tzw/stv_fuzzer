"""Domain-neutral mutation selectors."""

import random
from collections.abc import Callable

from fuzzer.mutator.base import MutationOperation, MutationStrategy


class RandomSingleStrategy(MutationStrategy):
    """Pick one random operation from a provided operation set."""

    def __init__(self, operations: list[MutationOperation]):
        if not operations:
            raise ValueError("RandomSingleStrategy requires at least one operation")
        self.operations = operations

    def select(self) -> list[MutationOperation]:
        return [random.choice(self.operations)]


class RoundRobinStrategy(MutationStrategy):
    """Cycle through operations in a fixed repeating order."""

    def __init__(self, operations: list[MutationOperation]):
        if not operations:
            raise ValueError("RoundRobinStrategy requires at least one operation")
        self.operations = operations
        self._next_index = 0

    def select(self) -> list[MutationOperation]:
        operation = self.operations[self._next_index]
        self._next_index = (self._next_index + 1) % len(self.operations)
        return [operation]


SELECTOR_FACTORIES: dict[str, Callable[..., MutationStrategy]] = {
    "random_single": RandomSingleStrategy,
    "round_robin": RoundRobinStrategy,
}

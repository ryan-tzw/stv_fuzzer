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


class HybridStrategy(MutationStrategy):
    """
    Hybrid strategy.
    - Phase 1: ALWAYS apply one tree mutation first .
    - Phase 2: With 30% probability, ALSO apply one string mutation on top.
    """

    def __init__(self, operations: list[MutationOperation]):
        if not operations:
            raise ValueError("HybridStrategy requires at least one operation")

        self.tree_operations = [op for op in operations if op.kind == "tree"]
        self.string_operations = [op for op in operations if op.kind == "string"]
        self.string_probability = 0.3

    def select(self) -> list[MutationOperation]:
        tree_op = random.choice(self.tree_operations)
        ops_to_apply = [tree_op]
        if random.random() < self.string_probability:
            string_op = random.choice(self.string_operations)
            ops_to_apply.append(string_op)

        return ops_to_apply


SELECTOR_FACTORIES: dict[str, Callable[..., MutationStrategy]] = {
    "random_single": RandomSingleStrategy,
    "round_robin": RoundRobinStrategy,
    "hybrid": HybridStrategy,
}

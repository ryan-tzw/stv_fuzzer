"""Domain-neutral mutation selectors."""

import random
import math
from collections.abc import Callable

from fuzzer.mutator.base import MutationOperation, MutationStrategy


class RandomSingleStrategy(MutationStrategy):
    """Pick one random operation from a provided operation set."""

    def __init__(self, operations: list[MutationOperation]):
        if not operations:
            raise ValueError("RandomSingleStrategy requires at least one operation")
        self.operations = operations

    def select(self) -> list[MutationOperation]:
        total = sum(op.weight for op in self.operations)
        weights = [op.weight / total for op in self.operations]
        return [random.choices(self.operations, weights=weights, k=1)[0]]

    def update_weight(self, op: MutationOperation, reward: float = 0.0) -> None:
        """Lightweight MOpt-style PSO update."""
        decay = 0.995
        eta = 0.08
        exploration_std = 0.02
        for o in self.operations:
            o.weight *= decay
        r = math.tanh(reward)
        op.weight *= math.exp(eta * r)
        op.weight += random.gauss(0, exploration_std * abs(op.weight))
        op.weight = max(0.1, min(10.0, op.weight))


class RoundRobinStrategy(MutationStrategy):
    """Cycle through operations in a fixed repeating order.(weights ignored)"""

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
        tree_total = sum(op.weight for op in self.tree_operations)
        tree_weights = [op.weight / tree_total for op in self.tree_operations]
        tree_op = random.choices(self.tree_operations, weights=tree_weights, k=1)[0]
        ops_to_apply = [tree_op]

        if random.random() < self.string_probability:
            string_total = sum(op.weight for op in self.string_operations)
            string_weights = [op.weight / string_total for op in self.string_operations]
            string_op = random.choices(
                self.string_operations, weights=string_weights, k=1
            )[0]
            ops_to_apply.append(string_op)

        return ops_to_apply

    def update_weight(self, op: MutationOperation, reward: float = 0.0) -> None:
        """Lightweight MOpt-style PSO update."""
        decay = 0.995
        eta = 0.08
        exploration_std = 0.02
        all_ops = self.tree_operations + self.string_operations
        for o in all_ops:
            o.weight *= decay
        r = math.tanh(reward)
        op.weight *= math.exp(eta * r)
        op.weight += random.gauss(0, exploration_std * abs(op.weight))
        op.weight = max(0.1, min(10.0, op.weight))


SELECTOR_FACTORIES: dict[str, Callable[..., MutationStrategy]] = {
    "random_single": RandomSingleStrategy,
    "round_robin": RoundRobinStrategy,
    "hybrid": HybridStrategy,
}

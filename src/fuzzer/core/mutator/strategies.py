"""
Mutation strategies that determine how operations are selected and applied.
"""

import random
from abc import ABC, abstractmethod
from collections.abc import Callable

from .operations import (
    DeleteChar,
    DuplicateChar,
    InsertRandomChar,
    MutationOperation,
    RandomiseChar,
)

ALL_OPERATIONS: list[type[MutationOperation]] = [
    RandomiseChar,
    DeleteChar,
    InsertRandomChar,
    DuplicateChar,
]


class MutationStrategy(ABC):
    @abstractmethod
    def select(self) -> list[MutationOperation]:
        """Return the list of operations to apply for this mutation."""
        ...


class RandomSingleStrategy(MutationStrategy):
    """Pick one random operation from all available operations."""

    def __init__(self, operations: list[type[MutationOperation]] = ALL_OPERATIONS):
        self.operations = operations

    def select(self) -> list[MutationOperation]:
        return [random.choice(self.operations)()]


STRATEGY_FACTORIES: dict[str, Callable[[], MutationStrategy]] = {
    "random_single": RandomSingleStrategy,
}

AVAILABLE_STRATEGIES: tuple[str, ...] = tuple(STRATEGY_FACTORIES.keys())


def build_strategy(name: str) -> MutationStrategy:
    """Build and return a mutation strategy by name."""
    try:
        return STRATEGY_FACTORIES[name]()
    except KeyError as exc:
        available = ", ".join(sorted(STRATEGY_FACTORIES))
        raise ValueError(
            f"Unknown mutation strategy: {name!r}. Available: {available}"
        ) from exc

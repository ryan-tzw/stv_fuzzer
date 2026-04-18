"""Base mutator interfaces shared across data domains."""

from __future__ import annotations
from abc import ABC, abstractmethod


class BaseMutator(ABC):
    @abstractmethod
    def mutate(self, data: str) -> tuple[str, list[MutationOperation]]:
        """Mutate input text and return (mutated_data, list_of_operations_used)"""
        ...

    def update_weights(
        self, operations: list[MutationOperation], reward: float = 0.0
    ) -> None:
        """Update weights of the operations that were used in this mutation."""
        pass


class MutationOperation(ABC):
    kind: str = "unknown"
    weight: float = 1.0

    @abstractmethod
    def mutate(self, data: str) -> str:
        """Apply one mutation operation to input text."""
        ...


class MutationStrategy(ABC):
    @abstractmethod
    def select(self) -> list[MutationOperation]:
        """Return operations to apply for one mutation step."""
        ...

    def update_weight(self, op: MutationOperation, reward: float = 0.0) -> None:
        """Update an operation's weight based on fuzzing feedback (coverage/crash)."""
        ...

    def apply_decay(self) -> None:
        """Apply global decay to all known operations once per mutation batch."""
        pass

    def get_fallback_operations(self) -> list[MutationOperation]:
        """Return string-based operations to use as fallback"""
        return []

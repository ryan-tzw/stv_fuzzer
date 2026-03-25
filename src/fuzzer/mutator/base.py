"""Base mutator interfaces shared across data domains."""

from abc import ABC, abstractmethod


class MutationOperation(ABC):
    @abstractmethod
    def mutate(self, data: str) -> str:
        """Apply one mutation operation to input text."""
        ...


class MutationStrategy(ABC):
    @abstractmethod
    def select(self) -> list[MutationOperation]:
        """Return operations to apply for one mutation step."""
        ...

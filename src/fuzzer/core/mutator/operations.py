"""
Primitive mutation operations that can be applied to a string input.
"""

import random
import string
from abc import ABC, abstractmethod


class MutationOperation(ABC):
    @abstractmethod
    def mutate(self, data: str) -> str:
        """Apply the mutation to the input string and return the result."""
        ...


class RandomiseChar(MutationOperation):
    """Replace a random character with a random printable ASCII character."""

    def mutate(self, data: str) -> str:
        if not data:
            return data
        idx = random.randrange(len(data))
        new_char = random.choice(string.printable)
        return data[:idx] + new_char + data[idx + 1 :]


class DeleteChar(MutationOperation):
    """Delete a random character from the input."""

    def mutate(self, data: str) -> str:
        if not data:
            return data
        idx = random.randrange(len(data))
        return data[:idx] + data[idx + 1 :]


class InsertRandomChar(MutationOperation):
    """Insert a random printable ASCII character at a random position."""

    def mutate(self, data: str) -> str:
        idx = random.randint(0, len(data))
        new_char = random.choice(string.printable)
        return data[:idx] + new_char + data[idx:]


class DuplicateChar(MutationOperation):
    """Duplicate a random character in the input."""

    def mutate(self, data: str) -> str:
        if not data:
            return data
        idx = random.randrange(len(data))
        return data[:idx] + data[idx] + data[idx:]

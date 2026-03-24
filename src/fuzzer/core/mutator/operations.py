"""
Primitive mutation operations that can be applied to a string input.
"""

import random
import string
from abc import ABC, abstractmethod


class MutationOperation(ABC):
    @abstractmethod
    def mutate(self, data: str, rng: random.Random) -> str:
        """Apply the mutation to the input string and return the result."""
        ...


# Character-level Mutations
class RandomiseChar(MutationOperation):
    """Replace a random character with a random printable ASCII character."""

    def mutate(self, data: str, rng: random.Random) -> str:
        if not data:
            return data
        idx = rng.randrange(len(data))
        new_char = rng.choice(string.printable)
        return data[:idx] + new_char + data[idx + 1 :]


class DeleteChar(MutationOperation):
    """Delete a random character from the input."""

    def mutate(self, data: str, rng: random.Random) -> str:
        if not data:
            return data
        idx = rng.randrange(len(data))
        return data[:idx] + data[idx + 1 :]


class InsertRandomChar(MutationOperation):
    """Insert a random printable ASCII character at a random position."""

    def mutate(self, data: str, rng: random.Random) -> str:
        idx = rng.randint(0, len(data))
        new_char = rng.choice(string.printable)
        return data[:idx] + new_char + data[idx:]


class DuplicateChar(MutationOperation):
    """Duplicate a random character in the input."""

    def mutate(self, data: str, rng: random.Random) -> str:
        if not data:
            return data
        idx = rng.randrange(len(data))
        return data[:idx] + data[idx] + data[idx:]


class AppendChar(MutationOperation):
    """Append a random printable character to the end of the string."""

    def mutate(self, data: str, rng: random.Random) -> str:
        return data + rng.choice(string.printable)


class PrependChar(MutationOperation):
    """Prepend a random printable character to the start of the string."""

    def mutate(self, data: str, rng: random.Random) -> str:
        return rng.choice(string.printable) + data


class GenerateIdentifier(MutationOperation):
    """Generates a random valid-looking identifier if the input is empty."""

    def mutate(self, data: str, rng: random.Random) -> str:
        alphabet = string.ascii_lowercase
        chars = alphabet + string.digits + "_"
        length = rng.randint(1, 8)
        first = rng.choice(alphabet + "_")
        rest = "".join(rng.choice(chars) for _ in range(length - 1))
        return first + rest

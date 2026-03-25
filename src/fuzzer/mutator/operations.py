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


class GrammarSubtreeReplace(MutationOperation):
    """Mutate text by parsing to a Node tree and replacing one subtree."""

    def __init__(self, grammar_name: str = "ipv4"):
        self.grammar_name = grammar_name
        self._parser = None
        self._pool = None
        from fuzzer.grammar.grammar_mutator import GrammarMutator

        self._mutator = GrammarMutator()

    def _ensure_runtime(self) -> None:
        if self._parser is None:
            from fuzzer.grammar.loader import load_parser

            self._parser = load_parser(self.grammar_name)
        if self._pool is None:
            from fuzzer.grammar.fragments import FragmentPool

            self._pool = FragmentPool()

    def mutate(self, data: str) -> str:
        try:
            self._ensure_runtime()
            from fuzzer.grammar.parser import parse_input
            from fuzzer.grammar.serializer import serialize_tree

            assert self._parser is not None
            assert self._pool is not None

            parsed = parse_input(self._parser, data)
            if not parsed.success or parsed.tree is None:
                return data

            self._pool.add_tree(parsed.tree)
            mutated = self._mutator.mutate_tree(parsed.tree, self._pool)
            if mutated is None:
                return data

            return serialize_tree(mutated)
        except Exception:
            return data

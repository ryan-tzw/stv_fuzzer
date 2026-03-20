"""
Mutation strategies that determine how operations are selected and applied.
"""

import random
from typing import Any
from abc import ABC, abstractmethod

from .operations import (
    DeleteChar,
    DuplicateChar,
    InsertRandomChar,
    MutationOperation,
    RandomiseChar,
    AppendChar,
    PrependChar,
)

CHAR_OPERATIONS: list[type[MutationOperation]] = [
    DeleteChar,
    DuplicateChar,
    InsertRandomChar,
    RandomiseChar,
    AppendChar,
    PrependChar,
]


class MutationStrategy(ABC):
    @abstractmethod
    def apply(self, data: str, rng: random.Random, depth: int = 1) -> str:
        """Apply 'depth' mutation and return the new string."""
        pass


class BlindRandomStrategy(MutationStrategy):
    """Original "dumb" strategy: randomly pick one primitive string operation."""

    def __init__(self, operations: list[type[MutationOperation]] = CHAR_OPERATIONS):
        self.operations = operations

    def apply(self, data: str, rng: random.Random, depth: int = 1) -> str:
        """Pick a random operation class and execute it."""
        for _ in range(depth):
            op_class = rng.choice(self.operations)
            operation = op_class()
            data = operation.mutate(data, rng)
        return data


class GrammarStrategy(MutationStrategy):
    """
    Smart strategy: parse → AST mutation (structural or token) → unparse.
    Falls back if the input is not valid for the chosen grammar.
    """

    def __init__(self, parser: Any, grammar_engine: Any, structure_bias: float = 0.5):
        self.parser = parser
        self.grammar_engine = grammar_engine
        self.structure_bias = structure_bias

    def apply(self, data: str, rng: random.Random, depth: int = 1) -> str:
        try:
            ast = self.parser.parse(data)
            self.grammar_engine.rng = rng
            mutated_ast = self.grammar_engine.mutate_n(
                ast, count=depth, structure_bias=self.structure_bias
            )
            return self.parser.unparse(mutated_ast)
        except Exception:
            return data

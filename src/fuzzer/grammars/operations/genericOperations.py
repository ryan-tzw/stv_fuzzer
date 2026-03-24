"""
Generic Grammar Operations - Shared mutation engine for all grammars.

This class provides a baseline implementation of apply_structure_mutation and
apply_token_mutation that work with generic AST structures. Grammars can extend
this class to add grammar-specific mutations.

Generic mutations include:
- Structure: Shuffle, Reverse, Rotate, Swap children (already in base)
- Token: Simple numeric/string mutations
"""

from __future__ import annotations

import random
import string

from ..astBuilder import AstNode
from .grammarOperation import (
    GrammarOperations,
    TokenMutationOperation,
    ShuffleChildren,
)


# Generic Token Operations
class MutateNumeric(TokenMutationOperation):
    """Generic mutation for any numeric token (int or float)."""

    def __init__(
        self,
        delta_float_range: tuple[float, float] = (-100.0, 100.0),
        delta_int_range: tuple[int, int] = (-100, 100),
        fallback_range: tuple[int, int] = (-9999, 9999),
    ):
        self.delta_float_range = delta_float_range
        self.delta_int_range = delta_int_range
        self.fallback_range = fallback_range

    def mutate(self, text: str, rng: random.Random) -> str:
        try:
            if any(ch in text for ch in ".eE"):
                value = float(text)
                delta = rng.uniform(*self.delta_float_range)
                if abs(delta) < 1e-9:
                    delta = 1.0
                return format(value + delta, ".12g")
            else:
                value = int(text)
                delta = rng.randint(*self.delta_int_range)
                if delta == 0:
                    delta = 1
                return str(value + delta)
        except Exception:
            return str(rng.randint(*self.fallback_range))


class MutateString(TokenMutationOperation):
    """Generic mutation for string tokens - inject random characters."""

    def __init__(self, charset: str | None = None):
        self.charset = charset or (string.ascii_letters + string.digits + "_")

    def mutate(self, text: str, rng: random.Random) -> str:
        """Insert a random character at a random position."""
        if not text:
            text = self.charset[0]

        pos = rng.randrange(len(text) + 1)
        char = rng.choice(self.charset)
        return text[:pos] + char + text[pos:]


class MutateHexadecimal(TokenMutationOperation):
    """Generic mutation for hexadecimal tokens (e.g., IPv6 segments)."""

    def mutate(self, text: str, rng: random.Random) -> str:
        try:
            value = int(text, 16)
        except ValueError:
            value = rng.randint(0, 0xFFFF)

        delta = rng.randint(-0x1000, 0x1000)
        if delta == 0:
            delta = 1

        value = (value + delta) % 0x10000
        out = format(value, "x")

        # Try to preserve case if the original had a pattern
        if text.isupper():
            out = out.upper()
        elif text.islower():
            out = out.lower()

        return out


# Generic Grammar Engine
class GenericGrammarOperations(GrammarOperations):
    """
    Generic mutation engine that works with any AST.

    Provides default structural and token mutations that apply to generic ASTs.
    Subclasses should override apply_structure_mutation / apply_token_mutation
    for grammar-specific behavior.
    """

    def __init__(self, rng_seed: int | None = None):
        super().__init__(rng_seed=rng_seed)

        # Generic token operations
        self.mutate_numeric = MutateNumeric()
        self.mutate_string = MutateString()
        self.mutate_hex = MutateHexadecimal()

        # Generic structure operations
        self.shuffle = ShuffleChildren()

    def apply_structure_mutation(self, root: AstNode) -> bool:
        """
        Generic structure mutation: shuffle children of nodes.

        Subclasses should override for grammar-specific operations.
        """
        # Find all internal nodes (with children)
        internal_nodes = self.internal_nodes(root)

        if not internal_nodes:
            return False

        # Try to shuffle each one
        self.rng.shuffle(internal_nodes)
        for node in internal_nodes:
            if self.shuffle.mutate(node, self.rng):
                return True

        return False

    def apply_token_mutation(self, root: AstNode) -> bool:
        """
        Generic token mutation: mutate leaf nodes with values.

        Strategy:
        - Numeric-looking leaves (all digits/dots) → numeric mutation
        - Hex-looking (0-9a-fA-F) → hex mutation
        - Otherwise → string mutation
        """
        # Find all leaf nodes with values
        leaf_nodes = [
            node
            for node in self.leaf_nodes(root)
            if node.value is not None and str(node.value).strip()
        ]

        if not leaf_nodes:
            return False

        node = self.rng.choice(leaf_nodes)
        value_str = str(node.value).strip()

        # Classify and apply appropriate mutation
        if self._is_numeric(value_str):
            node.value = self.mutate_numeric.mutate(value_str, self.rng)
            return True

        if self._is_hex(value_str):
            node.value = self.mutate_hex.mutate(value_str, self.rng)
            return True

        # Default to string mutation
        node.value = self.mutate_string.mutate(value_str, self.rng)
        return True

    def _is_numeric(self, text: str) -> bool:
        """Check if text looks like a number (int or float)."""
        try:
            float(text)
            return True
        except ValueError:
            return False

    def _is_hex(self, text: str) -> bool:
        """Check if text looks like hexadecimal."""
        if not text:
            return False
        # Check if all characters are hex digits
        return all(c in "0123456789abcdefABCDEF" for c in text)

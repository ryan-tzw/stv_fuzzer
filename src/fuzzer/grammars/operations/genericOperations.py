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

    def __init__(self, rng_seed: int | None = None, validity_mode: int = 0):
        super().__init__(rng_seed=rng_seed, validity_mode=validity_mode)

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
        if self.rng.random() < 0.8:
            if self.apply_type_aware_crossover(root):
                return True

        if self.should_produce_malformed() or self.rng.random() < 0.2:
            internal_nodes = self.internal_nodes(root)
            if not internal_nodes:
                return False

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
        - In malformed modes, more aggressive corruption applied
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

        # Apply mode-aware corruption
        if self.should_produce_malformed():
            # Aggressive corruption: random character injection or replacement
            if self.rng.random() < 0.5:
                node.value = self._corrupt_value(value_str)
            else:
                node.value = self.mutate_string.mutate(value_str, self.rng)
            return True

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

    def _corrupt_value(self, text: str) -> str:
        """Aggressively corrupt a value by random injection/replacement."""
        if not text:
            return "CORRUPT"
        charset = string.ascii_letters + string.digits + string.punctuation
        if self.rng.random() < 0.5:
            # Random insertion
            pos = self.rng.randrange(len(text) + 1)
            char = self.rng.choice(charset)
            return text[:pos] + char + text[pos:]
        else:
            # Random replacement
            pos = self.rng.randrange(len(text))
            char = self.rng.choice(charset)
            return text[:pos] + char + text[pos + 1 :]

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


if __name__ == "__main__":
    from pathlib import Path
    from ..parser.parser import create_parser

    ANTLR_DIR = (Path(__file__).parent.parent / "antlr").resolve()

    print("=" * 60)
    print("\nARITHMETIC GENERIC OPERATIONS TESTS")
    print("-" * 60)

    arith_parser = create_parser("arithmetic", ANTLR_DIR)
    ops = GenericGrammarOperations(rng_seed=42, validity_mode=0)

    arith_tests = [
        "1+2*3",
        "(4-5)/6",
        "10",
        "2*(3+4)",
        "100-20+3*4/2",
        "(1+2)*(3-4)",
        "42/7+8*9",
        "123+456*789-0",
        "(10+20)*(30/5)-7",
    ]

    print("\n=== SANITY: PARSE → UNPARSE ===")
    for expr in arith_tests:
        print(f"\nInput     : {expr}")
        try:
            ast = arith_parser.parse(expr)
            out = arith_parser.unparse(ast)
            print(f"Unparsed  : {out}")
        except Exception as e:
            print(f"FAILED    : {e}")

    print("\n=== TOKEN MUTATION TESTS ===")
    for expr in arith_tests:
        print(f"\nOriginal  : {expr}")
        try:
            ast = arith_parser.parse(expr)

            mutated = ops.clone(ast)
            success = ops.apply_token_mutation(mutated)

            print(f"Mutation applied: {success}")
            out = arith_parser.unparse(mutated)
            print(f"Mutated   : {out}")

            # Re-parse validation
            try:
                arith_parser.parse(out)
                print("Re-parse  : OK")
            except Exception:
                print("Re-parse  : FAILED")

        except Exception as e:
            print(f"FAILED    : {e}")

    print("\n=== STRUCTURE MUTATION TESTS ===")
    for expr in arith_tests:
        print(f"\nOriginal  : {expr}")
        try:
            ast = arith_parser.parse(expr)

            mutated = ops.clone(ast)
            success = ops.apply_structure_mutation(mutated)

            print(f"Mutation applied: {success}")
            out = arith_parser.unparse(mutated)
            print(f"Mutated   : {out}")

            # Re-parse validation
            try:
                arith_parser.parse(out)
                print("Re-parse  : OK")
            except Exception:
                print("Re-parse  : FAILED")

        except Exception as e:
            print(f"FAILED    : {e}")

    print("\n=== FULL MUTATION (mutate) ===")
    for expr in arith_tests:
        print(f"\nSeed Input: {expr}")
        try:
            ast = arith_parser.parse(expr)

            for i in range(5):
                ast = ops.mutate(ast, structure_bias=0.5)
                out = arith_parser.unparse(ast)

                print(f"\nIteration {i + 1}: {out}")

                # Validate
                try:
                    arith_parser.parse(out)
                    print("Re-parse  : OK")
                except Exception:
                    print("Re-parse  : FAILED")

        except Exception as e:
            print(f"FAILED    : {e}")

    print("\n=== STRESS TEST (FUZZ LOOP) ===")
    base = "1+2*3-4/5"
    try:
        ast = arith_parser.parse(base)

        for i in range(10):
            ast = ops.mutate(ast)
            out = arith_parser.unparse(ast)

            print(f"{i:02d}: {out}")

            try:
                arith_parser.parse(out)
            except Exception:
                print("Re-parse: FAILED")

    except Exception as e:
        print(f"FAILED: {e}")

"""
Json Grammar Mutation
"""

from __future__ import annotations

import random
import string
import re
from typing import Callable, Any

from ..astBuilder import AstNode
from .grammarOperation import (
    AstMutationOperation,
    TokenMutationOperation,
    ShuffleChildren,
    ValidityMode,
)
from .genericOperations import GenericGrammarOperations


# JSON Ast Generator Helpers
class JsonAstGenerator:
    """
    Handles generation of random valid JSON AST nodes and keys.
    Used by structural mutations that need to insert new content.
    """

    def __init__(
        self,
        max_new_depth: int = 1,
        max_items: int = 10,
        num_range: tuple[int, int] = (-9999, 9999),
        type_weights: tuple[int, ...] = (
            4,
            3,
            2,
            1,
            1,
            1,
        ),  # String, Number, Boolean, Null, Array, Object
    ):
        self.max_new_depth = max_new_depth
        self.max_items = max_items
        self.num_range = num_range
        self.type_weights = type_weights
        self.types = ["String", "Number", "Boolean", "Null", "Array", "Object"]

    def random_identifier(
        self, rng: random.Random, min_len: int = 3, max_len: int = 10
    ) -> str:
        """Generate a safe JSON key name."""

        chars = string.ascii_lowercase + string.digits + "_"
        length = rng.randint(min_len, max_len)
        first = rng.choice(string.ascii_lowercase + "_")
        rest = "".join(rng.choice(chars) for _ in range(length - 1))
        return first + rest

    def unique_json_key(self, existing: set[str], rng: random.Random) -> str:
        """Guarantee a key that doesn't already exist in the object."""

        while True:
            candidate = self.random_identifier(rng, 3, 10)
            if candidate not in existing:
                return candidate

    def random_json_string(self, rng: random.Random) -> str | None:
        base = self.random_identifier(rng, 3, 8)
        if rng.random() < 0.5:
            base += rng.choice(string.ascii_letters)
        return base

    def random_json_value(self, depth: int, rng: random.Random) -> AstNode:
        """Recursively generate a random JSON value AST node."""
        if depth <= 0:
            choice = rng.choice(["String", "Number", "Boolean", "Null"])
        else:
            choice = rng.choices(population=self.types, weights=self.type_weights, k=1)[
                0
            ]

        if choice == "String":
            return AstNode("String", value=self.random_json_string(rng))
        if choice == "Number":
            return AstNode("Number", value=str(rng.randint(*self.num_range)))
        if choice == "Boolean":
            return AstNode("Boolean", value=bool(rng.getrandbits(1)))
        if choice == "Null":
            return AstNode("Null", value=None)
        if choice == "Array":
            count = rng.randint(0, self.max_items)
            return AstNode(
                "Array",
                children=[self.random_json_value(depth - 1, rng) for _ in range(count)],
            )
        if choice == "Object":
            count = rng.randint(0, 3)
            pairs, used = [], set()
            for _ in range(count):
                key = self.unique_json_key(used, rng)
                used.add(key)
                pairs.append(
                    AstNode(
                        "Pair",
                        children=[
                            AstNode("Key", value=key),
                            self.random_json_value(depth - 1, rng),
                        ],
                    )
                )
            return AstNode("Object", children=pairs)
        return AstNode("Null", value=None)


# JSON Token Operations
class MutateNumber(TokenMutationOperation):
    """Mutates a numeric token string (int or float) with validity control."""

    def __init__(
        self,
        delta_float_range: tuple[float, float] = (-100.0, 100.0),
        delta_int_range: tuple[int, int] = (-100, 100),
        fallback_range: tuple[int, int] = (-9999, 9999),
        validity_mode: int = 0,
    ):
        self.delta_float_range = delta_float_range
        self.delta_int_range = delta_int_range
        self.fallback_range = fallback_range
        self.validity_mode = ValidityMode(validity_mode)

    def mutate(self, text: str, rng: random.Random) -> str:
        if self.validity_mode == ValidityMode.WELL_FORMED:
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
        elif self.validity_mode == ValidityMode.SLIGHTLY_MALFORMED:
            # 30% chance to generate invalid number format
            if rng.random() < 0.3:
                return rng.choice(
                    [
                        "1.2.3",  # Multiple dots
                        "1e2e3",  # Multiple exponents
                        "1e",  # Incomplete exponent
                        ".5e+",  # Incomplete exponent
                    ]
                )
            else:
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
        else:  # HEAVILY_MALFORMED
            # 60% chance to generate extreme invalid numbers
            if rng.random() < 0.6:
                return rng.choice(
                    [
                        "NaN",
                        "Infinity",
                        "1.2.3.4.5",
                        "1e999e999",
                        "...",
                        "---",
                        "++1",
                    ]
                )
            else:
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


class EscapeString(TokenMutationOperation):
    """Inject random JSON escapes into a string value with validity control."""

    def __init__(self, escapes: list[str] | None = None, validity_mode: int = 0):
        # Default to standard JSON escapes if none provided
        self.escapes = escapes or [
            '\\"',
            "\\n",
            "\\t",
            "\\\\",
            "\\r",
            "\\b",
            "\\f",
        ]
        self.validity_mode = ValidityMode(validity_mode)

    def mutate(self, text: str, rng: random.Random) -> str:
        if self.validity_mode == ValidityMode.WELL_FORMED:
            tokens = re.findall(r'\\["\\/bfnrt]|\\u[0-9a-fA-F]{4}|.', text)
            pos = rng.randrange(len(tokens) + 1)
            tokens.insert(pos, rng.choice(self.escapes))
            return "".join(tokens)
        elif self.validity_mode == ValidityMode.SLIGHTLY_MALFORMED:
            # 30% chance to inject invalid escape
            if rng.random() < 0.3:
                tokens = re.findall(r'\\["\\/bfnrt]|\\u[0-9a-fA-F]{4}|.', text)
                pos = rng.randrange(len(tokens) + 1)
                invalid_escape = rng.choice(["\\x", "\\q", "\\@", "\\z"])
                tokens.insert(pos, invalid_escape)
                return "".join(tokens)
            else:
                tokens = re.findall(r'\\["\\/bfnrt]|\\u[0-9a-fA-F]{4}|.', text)
                pos = rng.randrange(len(tokens) + 1)
                tokens.insert(pos, rng.choice(self.escapes))
                return "".join(tokens)
        else:  # HEAVILY_MALFORMED
            # 60% chance to inject invalid/broken escape
            if rng.random() < 0.6:
                tokens = re.findall(r'\\["\\/bfnrt]|\\u[0-9a-fA-F]{4}|.', text)
                pos = rng.randrange(len(tokens) + 1)
                invalid_escape = rng.choice(
                    [
                        "\\",
                        "\\u",
                        "\\uXXXX",
                        "\\0",
                        "\\k",
                    ]
                )
                tokens.insert(pos, invalid_escape)
                return "".join(tokens)
            else:
                tokens = re.findall(r'\\["\\/bfnrt]|\\u[0-9a-fA-F]{4}|.', text)
                pos = rng.randrange(len(tokens) + 1)
                tokens.insert(pos, rng.choice(self.escapes))
                return "".join(tokens)


# JSON Structure Operations
class ObjectAddPair(AstMutationOperation):
    """Add a new key/value pair to an Object."""

    def __init__(self, generator: JsonAstGenerator):
        self.gen = generator

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if node.type != "Object":
            return False
        existing = {
            str(p.children[0].value)
            for p in node.children
            if p.type == "Pair" and p.children
        }
        key = self.gen.unique_json_key(existing, rng)
        val = self.gen.random_json_value(self.gen.max_new_depth, rng)
        node.children.append(AstNode("Pair", children=[AstNode("Key", value=key), val]))
        return True


class ObjectRemovePair(AstMutationOperation):
    """Remove a random key/value pair from an Object."""

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if node.type != "Object" or not node.children:
            return False
        idx = rng.randrange(len(node.children))
        del node.children[idx]
        return True


class ObjectDuplicatePair(AstMutationOperation):
    """Duplicate a pair (with a fresh unique key)."""

    def __init__(self, engine: Any, generator: JsonAstGenerator):
        self.engine = engine  # Need engine for cloning AST nodes
        self.gen = generator

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if node.type != "Object" or not node.children:
            return False
        dup = self.engine.clone(rng.choice(node.children))

        # Keep keys unique so the AST stays easy to unparse.
        existing = {
            str(p.children[0].value)
            for p in node.children
            if p.type == "Pair" and p.children
        }
        if dup and dup.children and dup.children[0].type == "Key":
            dup.children[0].value = self.gen.unique_json_key(existing, rng)

        node.children.append(dup)
        return True


class ArrayAddItem(AstMutationOperation):
    """Append a random value to an Array."""

    def __init__(self, generator: JsonAstGenerator):
        self.gen = generator

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if node.type != "Array":
            return False
        node.children.append(self.gen.random_json_value(self.gen.max_new_depth, rng))
        return True


class ArrayRemoveItem(AstMutationOperation):
    """Remove a random item from an Array."""

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if node.type != "Array" or not node.children:
            return False
        idx = rng.randrange(len(node.children))
        del node.children[idx]
        return True


class ArrayDuplicateItem(AstMutationOperation):
    """Duplicate a random item in an Array."""

    def __init__(self, engine: Any):
        self.engine = engine

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if node.type != "Array" or not node.children:
            return False
        dup = self.engine.clone(rng.choice(node.children))
        if dup:
            node.children.append(dup)
        return True


class SwapScalar(AstMutationOperation):
    """Replace a scalar value (string/number/boolean/null) with another random scalar."""

    def __init__(self, generator: JsonAstGenerator):
        self.gen = generator

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if node.type not in {"String", "Number", "Boolean", "Null"}:
            return False
        choice = rng.choice(["String", "Number", "Boolean", "Null"])
        if choice == "String":
            node.type = "String"
            node.value = self.gen.random_json_string(rng)
        elif choice == "Number":
            node.type = "Number"
            node.value = str(rng.randint(-1000000, 1000000))
        elif choice == "Boolean":
            node.type = "Boolean"
            node.value = rng.choice([True, False])
        elif choice == "Null":
            node.type = "Null"
            node.value = None
        return True


class DeepNesting(AstMutationOperation):
    """Wrap a random leaf in multiple Array layers (increases nesting depth)."""

    def __init__(self, engine: Any, depth_range: tuple[int, int] = (2, 5)):
        self.engine = engine
        self.depth_range = depth_range

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        leaves = [
            (n, p, i)
            for n, p, i in self.engine.iter_nodes(node)
            if p is not None and n.type in {"String", "Number", "Boolean", "Null"}
        ]
        if not leaves:
            return False
        target_node, parent, index = rng.choice(leaves)
        depth = rng.randint(*self.depth_range)
        new_subtree = self.engine.clone(target_node)
        for _ in range(depth):
            new_subtree = AstNode("Array", children=[new_subtree])
        parent.children[index] = new_subtree
        return True


class DuplicateKeyMalformed(AstMutationOperation):
    """Create duplicate keys in an Object (invalid JSON)."""

    def __init__(self, engine: Any):
        self.engine = engine

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if node.type != "Object" or not node.children:
            return False
        # Pick a pair and duplicate its key (creating invalid JSON)
        pair_idx = rng.randrange(len(node.children))
        pair = node.children[pair_idx]
        if pair.type != "Pair" or not pair.children or not pair.children[0].value:
            return False
        # Clone the pair but keep the same key
        dup = self.engine.clone(pair)
        node.children.append(dup)
        return True


class ExtremeNestingMalformed(AstMutationOperation):
    """Create pathologically deep nesting (for heavily malformed mode)."""

    def __init__(self, engine: Any, extreme_depth: int = 50):
        self.engine = engine
        self.extreme_depth = extreme_depth

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        leaves = [
            (n, p, i)
            for n, p, i in self.engine.iter_nodes(node)
            if p is not None and n.type in {"String", "Number", "Boolean", "Null"}
        ]
        if not leaves:
            return False
        target_node, parent, index = rng.choice(leaves)
        new_subtree = self.engine.clone(target_node)
        # Create extreme nesting
        for _ in range(self.extreme_depth):
            new_subtree = AstNode("Array", children=[new_subtree])
        parent.children[index] = new_subtree
        return True


# The JSON Grammar Engine
class JsonGrammarOperations(GenericGrammarOperations):
    """JSON-specific mutation engine extending generic operations."""

    def __init__(
        self,
        rng_seed: int | None = None,
        max_new_depth: int = 1,
        inline_replace_depth: int = 2,
        validity_mode: int = 0,
    ):
        super().__init__(rng_seed=rng_seed, validity_mode=validity_mode)
        self.inline_replace_depth = inline_replace_depth
        self.gen = JsonAstGenerator(max_new_depth)

        # Token Operations
        self.mutate_number = MutateNumber(validity_mode=validity_mode)
        self.escape_string = EscapeString(validity_mode=validity_mode)

        # Structure Operations
        self.shuffle = ShuffleChildren()
        self.obj_add = ObjectAddPair(self.gen)
        self.obj_rm = ObjectRemovePair()
        self.obj_dup = ObjectDuplicatePair(self, self.gen)
        self.arr_add = ArrayAddItem(self.gen)
        self.arr_rm = ArrayRemoveItem()
        self.arr_dup = ArrayDuplicateItem(self)
        self.swap_scalar = SwapScalar(self.gen)
        self.deep_nest = DeepNesting(self)
        self.dup_key = DuplicateKeyMalformed(self)
        self.extreme_nest = ExtremeNestingMalformed(self)

    def _safe_replace_value(self, root: AstNode) -> bool:
        """Safely replace a JSON value node with a new random JSON value."""
        valid_types = {"String", "Number", "Boolean", "Null", "Array", "Object"}
        nodes = [
            (n, p, i)
            for n, p, i in self.iter_nodes(root)
            if p is not None and i is not None and n.type in valid_types
        ]
        if not nodes:
            return False
        node, parent, index = self._weighted_choice(nodes)
        parent.children[index] = self.gen.random_json_value(
            self.inline_replace_depth, self.rng
        )
        return True

    # Structure Mutation
    def apply_structure_mutation(self, root: AstNode) -> bool:
        """
        Collect & execute one successful structural action.
        In malformed modes, prioritize malforming operations.
        """
        actions: list[Callable[[], bool]] = []

        for node, _, _ in self.iter_nodes(root):
            if node.type == "Object":
                actions.extend(
                    [
                        lambda n=node: self.obj_add.mutate(n, self.rng),
                        lambda n=node: self.obj_rm.mutate(n, self.rng),
                        lambda n=node: self.obj_dup.mutate(n, self.rng),
                        lambda n=node: self.shuffle.mutate(n, self.rng),
                    ]
                )
                # Add malformed operations for non-well-formed modes
                if self.validity_mode != ValidityMode.WELL_FORMED:
                    actions.append(lambda n=node: self.dup_key.mutate(n, self.rng))
            elif node.type == "Array":
                actions.extend(
                    [
                        lambda n=node: self.arr_add.mutate(n, self.rng),
                        lambda n=node: self.arr_rm.mutate(n, self.rng),
                        lambda n=node: self.arr_dup.mutate(n, self.rng),
                        lambda n=node: self.shuffle.mutate(n, self.rng),
                    ]
                )
            elif node.type in {"String", "Number", "Boolean"}:
                actions.append(lambda n=node: self.swap_scalar.mutate(n, self.rng))

        # Global actions
        actions.append(lambda: self.deep_nest.mutate(root, self.rng))
        if self.validity_mode == ValidityMode.HEAVILY_MALFORMED:
            actions.append(lambda: self.extreme_nest.mutate(root, self.rng))
        actions.append(lambda: self._safe_replace_value(root))

        self.rng.shuffle(actions)
        for action in actions:
            if action():
                return True
        return False

    def apply_token_mutation(self, root: AstNode) -> bool:
        """Mutate either a Number or a String/Key."""
        target_nodes = [
            n
            for n, _, _ in self.iter_nodes(root)
            if n.type in {"String", "Key", "Number"} and n.value is not None
        ]
        if not target_nodes:
            return False
        node = self.rng.choice(target_nodes)
        # Apply the matching token operation
        if node.type == "Number":
            node.value = self.mutate_number.mutate(str(node.value), self.rng)
            return True
        if node.type in {"String", "Key"}:
            node.value = self.escape_string.mutate(str(node.value), self.rng)
            return True
        return False


if __name__ == "__main__":
    from pathlib import Path
    from ..parser.parser import jsonParser

    # Setup parser
    ANTLR_DIR = (Path(__file__).parent.parent / "antlr").resolve()
    parser = jsonParser(ANTLR_DIR)

    def print_case(title, value):
        print(f"\n{title}")
        print("-" * 50)
        print(value)

    # Test inputs
    json_tests = [
        # Simple
        '{"a": 1}',
        '{"name": "Alice", "age": 30}',
        "[1,2,3,4]",
        "true",
        "false",
        "null",
        # Mixed types
        '{"a": 1, "b": true, "c": null}',
        '{"arr": [1, "x", false]}',
        # Nested
        '{"nested": {"x": 1, "y": [10,20]}}',
        '{"deep": {"a": {"b": {"c": [1,2,3]}}}}',
        # Edge-ish
        '{"empty_obj": {}, "empty_arr": []}',
        '{"unicode": "hello"}',
    ]

    # Initialize operations
    ops = JsonGrammarOperations(rng_seed=42, validity_mode=1)

    print("\n=== SANITY: PARSE → UNPARSE ===")
    for js in json_tests:
        print_case("Input", js)
        try:
            ast = parser.parse(js)
            out = parser.unparse(ast)
            print("Unparsed:", out)
        except Exception as e:
            print("FAILED:", e)

    print("\n=== TOKEN MUTATION TESTS ===")
    for js in json_tests:
        print_case("Original", js)
        try:
            ast = parser.parse(js)

            mutated = ops.clone(ast)
            success = ops.apply_token_mutation(mutated)

            print("Mutation applied:", success)
            out = parser.unparse(mutated)
            print("Mutated:", out)

            # Re-parse validation
            try:
                parser.parse(out)
                print("Re-parse: OK")
            except Exception:
                print("Re-parse: FAILED")

        except Exception as e:
            print("FAILED:", e)

    print("\n=== STRUCTURE MUTATION TESTS ===")
    for js in json_tests:
        print_case("Original", js)
        try:
            ast = parser.parse(js)

            mutated = ops.clone(ast)
            success = ops.apply_structure_mutation(mutated)

            print("Mutation applied:", success)
            out = parser.unparse(mutated)
            print("Mutated:", out)

            # Re-parse validation
            try:
                parser.parse(out)
                print("Re-parse: OK")
            except Exception:
                print("Re-parse: FAILED")

        except Exception as e:
            print("FAILED:", e)

    print("\n=== FULL MUTATION (mutate) ===")
    for js in json_tests:
        print_case("Seed Input", js)
        try:
            ast = parser.parse(js)

            for i in range(5):
                ast = ops.mutate(ast, structure_bias=0.5)
                out = parser.unparse(ast)

                print(f"\nIteration {i + 1}: {out}")

                # Validate
                try:
                    parser.parse(out)
                    print("Re-parse: OK")
                except Exception:
                    print("Re-parse: FAILED")

        except Exception as e:
            print("FAILED:", e)

    print("\n=== STRESS TEST (FUZZ LOOP) ===")
    base = r'{"a": true, "b": [1,2,3, null], "c": {"d" : null}}'

    try:
        ast = parser.parse(base)

        for i in range(50):
            ast = ops.mutate(ast)
            out = parser.unparse(ast)

            print(f"{i:02d}: {out}")

            try:
                parser.parse(out)
            except Exception:
                print("Re-parse: FAILED")

    except Exception as e:
        print("FAILED:", e)

    print("\n=== ALL TESTS DONE ===")

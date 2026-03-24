"""
IP Address (IPv4 / IPv6) Grammar Mutation
"""

from __future__ import annotations

import random
from typing import Callable

from ..astBuilder import AstNode
from .grammarOperation import (
    AstMutationOperation,
    TokenMutationOperation,
    ShuffleChildren,
    ValidityMode,
)
from .genericOperations import GenericGrammarOperations


# IP-Specific Token Operations
class MutateOctet(TokenMutationOperation):
    """Mutates an IPv4 octet (0-255) with optional edge-case injection and validity control."""

    def __init__(self, validity_mode: int = 0):
        self.validity_mode = ValidityMode(validity_mode)

    def mutate(self, text: str, rng: random.Random) -> str:
        try:
            value = int(text, 10)
        except Exception:
            value = rng.randint(0, 255)

        # Validity-aware mutation
        if self.validity_mode == ValidityMode.WELL_FORMED:
            # Classic edge-case values
            if rng.random() < 0.10:
                return str(rng.choice([0, 255]))
            delta = rng.randint(-50, 50)
            if delta == 0:
                delta = 1
            value = max(0, min(255, value + delta))
        elif self.validity_mode == ValidityMode.SLIGHTLY_MALFORMED:
            # 40% chance to generate invalid octet (256-512)
            if rng.random() < 0.4:
                value = rng.randint(256, 512)
            else:
                delta = rng.randint(-50, 50)
                if delta == 0:
                    delta = 1
                value = max(0, min(255, value + delta))
        else:  # HEAVILY_MALFORMED
            # 70% chance to generate extreme values
            if rng.random() < 0.7:
                value = rng.choice(
                    [
                        rng.randint(256, 9999),
                        rng.randint(-1000, -1),
                    ]
                )
            else:
                delta = rng.randint(-50, 50)
                if delta == 0:
                    delta = 1
                value = max(0, min(255, value + delta))

        # Preserve width sometimes so leading-zero style survives
        if len(text) > 1 and text.startswith("0"):
            return str(value).zfill(len(text))

        if rng.random() < 0.35:
            return str(value).zfill(max(1, len(text)))

        return str(value)


class MutateH16(TokenMutationOperation):
    """Mutates an IPv6 16-bit hex block with case and padding preservation and validity control."""

    def __init__(self, validity_mode: int = 0):
        self.validity_mode = ValidityMode(validity_mode)

    def mutate(self, text: str, rng: random.Random) -> str:
        # Validity-aware mutation
        if self.validity_mode == ValidityMode.WELL_FORMED:
            if rng.random() < 0.10:
                return rng.choice(["0", "ffff"])

            try:
                value = int(text, 16)
            except Exception:
                value = rng.randint(0, 0xFFFF)

            delta = rng.randint(-0x1000, 0x1000)
            if delta == 0:
                delta = 1

            value = (value + delta) % 0x10000
        elif self.validity_mode == ValidityMode.SLIGHTLY_MALFORMED:
            # 30% chance to generate invalid hex value
            if rng.random() < 0.3:
                value = rng.randint(0x10000, 0xFFFFFF)
            else:
                try:
                    value = int(text, 16)
                except Exception:
                    value = rng.randint(0, 0xFFFF)
                delta = rng.randint(-0x1000, 0x1000)
                if delta == 0:
                    delta = 1
                value = (value + delta) % 0x10000
        else:  # HEAVILY_MALFORMED
            # 70% chance to generate extreme hex value
            if rng.random() < 0.7:
                value = rng.randint(0x10000, 0xFFFFFFFF)
            else:
                try:
                    value = int(text, 16)
                except Exception:
                    value = rng.randint(0, 0xFFFF)
                delta = rng.randint(-0x1000, 0x1000)
                if delta == 0:
                    delta = 1
                value = (value + delta) % 0x10000

        out = format(value, "x")
        if text.isupper():
            out = out.upper()
        elif text.islower():
            out = out.lower()

        if rng.random() < 0.5 and len(out) < len(text):
            out = out.zfill(len(text))
        return out


# IP-Specific Structure Operations
class ToggleIpVersion(AstMutationOperation):
    """
    Swaps an IPv4 AST for an IPv6 AST and vice versa.
    IPv4 → IPv6 uses the ::ffff:a.b.c.d mapped form.
    IPv6 → IPv4 extracts the last two H16 blocks (if possible).
    """

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if node.type == "Ipv4":
            octets = [child.value for child in node.children if child.type == "Octet"]
            if len(octets) != 4:
                return False
            # Convert IPv4 to IPv6-mapped
            h16_1 = format((int(octets[0]) << 8) | int(octets[1]), "x")
            h16_2 = format((int(octets[2]) << 8) | int(octets[3]), "x")

            node.type = "Ipv6Compressed"
            node.children = [
                AstNode("DoubleColon"),
                AstNode("H16", value="ffff"),
                AstNode("H16", value=h16_1),
                AstNode("H16", value=h16_2),
            ]
            return True
        if node.type.startswith("Ipv6"):
            h16_values = [child.value for child in node.children if child.type == "H16"]
            if not h16_values:
                return False
            try:
                last = int(h16_values[-1], 16)
                second_last = int(h16_values[-2], 16) if len(h16_values) >= 2 else 0
                octets = [
                    str((second_last >> 8) & 0xFF),
                    str(second_last & 0xFF),
                    str((last >> 8) & 0xFF),
                    str(last & 0xFF),
                ]
                node.type = "Ipv4"
                node.children = [AstNode("Octet", value=o) for o in octets]
                return True
            except Exception:
                return False
        return False


class ReorderMovableChildren(AstMutationOperation):
    """
    Reorders only "movable" children (e.g. H16 blocks) while leaving
    structural nodes like DoubleColon untouched.
    """

    def __init__(self, movable_types: set[str]):
        self.movable_types = movable_types

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        movable_indices = [
            i
            for i, child in enumerate(node.children)
            if child.type in self.movable_types
        ]
        if len(movable_indices) < 2:
            return False
        movable_children = [node.children[i] for i in movable_indices]
        mode = rng.choice(["shuffle", "reverse", "rotate", "swap"])
        if mode == "shuffle":
            rng.shuffle(movable_children)
        elif mode == "reverse":
            movable_children.reverse()
        elif mode == "rotate":
            k = rng.randint(1, len(movable_children) - 1)
            movable_children = movable_children[k:] + movable_children[:k]
        elif mode == "swap":
            i, j = rng.sample(range(len(movable_children)), 2)
            movable_children[i], movable_children[j] = (
                movable_children[j],
                movable_children[i],
            )
        for idx, child in zip(movable_indices, movable_children):
            node.children[idx] = child
        return True


# IP-Specific Structure Operations
class NormalizeIpv6(AstMutationOperation):
    """
    Either expands a compressed IPv6 (with ::) into full form
    or compresses the longest zero-run into ::.
    """

    def _is_zero_h16(self, value: str) -> bool:
        """Treat '0', '00', '0000', etc. as zero (int(value, 16) == 0)."""
        if not value:
            return False
        try:
            return int(value, 16) == 0
        except ValueError:
            return False

    def _slot_count(self, children: list[AstNode]) -> int:
        """Each H16 = 1 slot, each embedded Ipv4 = 2 slots."""
        count = 0
        for c in children:
            if c.type == "H16":
                count += 1
            elif c.type == "Ipv4":
                count += 2
        return count

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if not node.type.startswith("Ipv6"):
            return False
        children = node.children
        has_double_colon = any(c.type == "DoubleColon" for c in children)
        if has_double_colon and rng.random() < 0.5:
            try:
                dc_idx = next(
                    i for i, c in enumerate(children) if c.type == "DoubleColon"
                )
            except StopIteration:
                return False
            before = children[:dc_idx]
            after = children[dc_idx + 1 :]
            slots_before = self._slot_count(before)
            slots_after = self._slot_count(after)
            missing = 8 - (slots_before + slots_after)
            if missing <= 0:
                return False
            zeros = [AstNode("H16", value="0") for _ in range(missing)]
            new_children = before + zeros + after
            node.type = "Ipv6Full"
            node.children = new_children
            return True
        else:
            # Find longest run of zero H16s (works even with Ipv4 at the end)
            best_start = -1
            best_len = 0
            i = 0
            while i < len(children):
                if children[i].type == "H16" and self._is_zero_h16(children[i].value):
                    j = i
                    while (
                        j < len(children)
                        and children[j].type == "H16"
                        and self._is_zero_h16(children[j].value)
                    ):
                        j += 1
                    run_len = j - i
                    if run_len > best_len:
                        best_len = run_len
                        best_start = i
                    i = j
                else:
                    i += 1
            if best_len < 2:
                return False
            new_children = []
            idx = 0
            while idx < len(children):
                if idx == best_start:
                    new_children.append(AstNode("DoubleColon"))
                    idx += best_len
                else:
                    new_children.append(children[idx])
                    idx += 1
            node.type = "Ipv6Compressed"
            node.children = new_children
            return True


class BreakIpv6Compression(AstMutationOperation):
    """Malform :: compression by removing it or duplicating it (invalid IPv6)."""

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if not node.type.startswith("Ipv6"):
            return False
        children = node.children
        double_colon_indices = [
            i for i, c in enumerate(children) if c.type == "DoubleColon"
        ]

        if not double_colon_indices:
            return False

        if rng.random() < 0.5:
            # Remove the :: (creates invalid IPv6 with gaps)
            idx = rng.choice(double_colon_indices)
            del children[idx]
            return True
        else:
            # Duplicate :: (multiple :: is invalid)
            idx = rng.choice(double_colon_indices)
            children.insert(idx, AstNode("DoubleColon"))
            return True


class InjectInvalidOctet(AstMutationOperation):
    """Inject an invalid octet into IPv4 for malformed mode."""

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if node.type != "Ipv4":
            return False
        octet_nodes = [
            i for i, child in enumerate(node.children) if child.type == "Octet"
        ]
        if not octet_nodes:
            return False
        idx = rng.choice(octet_nodes)
        # Set to out-of-range value
        node.children[idx].value = str(rng.randint(256, 999))
        return True


# IP Grammar Engine
class IpGrammarOperations(GenericGrammarOperations):
    """IP-specific mutation engine extending generic operations."""

    def __init__(self, rng_seed: int | None = None, validity_mode: int = 0):
        super().__init__(rng_seed=rng_seed, validity_mode=validity_mode)

        # Token Mutation
        self.mutate_octet = MutateOctet(validity_mode=validity_mode)
        self.mutate_h16 = MutateH16(validity_mode=validity_mode)

        # Structural Mutation
        self.shuffle_op = ShuffleChildren()
        self.toggle_version_op = ToggleIpVersion()
        self.reorder_h16_op = ReorderMovableChildren({"H16"})
        self.normalize_ipv6_op = NormalizeIpv6()
        self.break_ipv6_op = BreakIpv6Compression()
        self.inject_invalid_octet_op = InjectInvalidOctet()

    # Structure Mutation Hook
    def apply_structure_mutation(self, root: AstNode) -> bool:
        """
        Collect all possible structural actions for every node,
        shuffle them, and execute the first one that succeeds.
        In malformed modes, prioritize malforming operations.
        """
        actions: list[Callable[[], bool]] = []

        for node, _, _ in self.iter_nodes(root):
            if node.type == "Ipv4":
                actions.append(lambda n=node: self.shuffle_op.mutate(n, self.rng))
                # Add invalid octet injection for malformed modes
                if self.validity_mode != ValidityMode.WELL_FORMED:
                    actions.append(
                        lambda n=node: self.inject_invalid_octet_op.mutate(n, self.rng)
                    )
            if node.type in {"Ipv6Full", "Ipv6Compressed"}:
                actions.append(lambda n=node: self.reorder_h16_op.mutate(n, self.rng))
                actions.append(
                    lambda n=node: self.normalize_ipv6_op.mutate(n, self.rng)
                )
                # Add compression breaking for malformed modes
                if self.validity_mode != ValidityMode.WELL_FORMED:
                    actions.append(
                        lambda n=node: self.break_ipv6_op.mutate(n, self.rng)
                    )
        # Always allow version toggle at the root level
        actions.append(lambda: self.toggle_version_op.mutate(root, self.rng))

        self.rng.shuffle(actions)
        for action in actions:
            if action():
                return True
        return False

    # Token mutation Hook
    def apply_token_mutation(self, root: AstNode) -> bool:
        """Pick a random Octet or H16 leaf and mutate its value."""
        nodes = [n for n, _, _ in self.iter_nodes(root) if n.type in {"Octet", "H16"}]
        if not nodes:
            return False
        node = self.rng.choice(nodes)

        if node.type == "Octet":
            node.value = self.mutate_octet.mutate(str(node.value), self.rng)
            return True
        if node.type == "H16":
            node.value = self.mutate_h16.mutate(str(node.value), self.rng)
            return True
        return False


if __name__ == "__main__":
    from pathlib import Path
    from ..parser.parser import ipParser

    # Setup Parser
    ANTLR_DIR = (Path(__file__).parent.parent / "antlr").resolve()
    parser = ipParser(ANTLR_DIR)

    def print_case(title, value):
        print(f"\n{title}")
        print("-" * 50)
        print(value)

    # Test Inputs
    ip_tests = [
        # IPv4
        "0.0.0.0",
        "00.01.002.000",
        "1.2.3.4",
        "127.0.0.1",
        "192.168.001.001",
        "255.255.255.255",
        # IPv6
        "2001:0db8:0000:0000:0000:ff00:0042:8329",
        "2001:db8::",
        "2001:db8::1",
        "2001:db8::192.0.2.33",
        "::192.0.2.33",
    ]

    # Initialize operations (seeded for reproducibility)
    ops = IpGrammarOperations(rng_seed=42, validity_mode=1)

    print("\n=== SANITY: PARSE → UNPARSE ===")
    for ip in ip_tests:
        print_case("Input", ip)
        try:
            ast = parser.parse(ip)
            out = parser.unparse(ast)
            print("Unparsed:", out)
        except Exception as e:
            print("FAILED:", e)

    print("\n=== TOKEN MUTATION TESTS ===")
    for ip in ip_tests:
        print_case("Original", ip)
        try:
            ast = parser.parse(ip)

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
    for ip in ip_tests:
        print_case("Original", ip)
        try:
            ast = parser.parse(ip)

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
    for ip in ip_tests:
        print_case("Seed Input", ip)
        try:
            ast = parser.parse(ip)

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
    base = "2001:db8::1"

    try:
        ast = parser.parse(base)

        for i in range(50):
            ast = ops.mutate(ast)
            out = parser.unparse(ast)

            print(f"{i:02d}: {out}")

            try:
                parser.parse(out)
            except Exception:
                print("Re-parse: FAILEDn")

    except Exception as e:
        print("FAILED:", e)

    print("\n=== ALL TESTS DONE ===")

"""
The core interfaces and shared utilities for mutating Abstract Syntax Trees (ASTs).
It supports two mutation categories: Structural mutations & Token mutations
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import IntEnum
import random
from typing import Callable, Iterator

from ..astBuilder import AstNode


class ValidityMode(IntEnum):
    """Validity control for generated inputs."""

    WELL_FORMED = 0  # Mostly valid inputs
    SLIGHTLY_MALFORMED = 1  # Mix of valid and near-valid with syntax issues
    HEAVILY_MALFORMED = 2  # Mostly invalid, syntactically incorrect


# AST Structural Operation Interfaces
class AstMutationOperation(ABC):
    """Base class for AST structure mutations."""

    @abstractmethod
    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        """Apply the mutation to the AST node in-place. Return True if successful."""
        pass


class GrammarAwareOperation(AstMutationOperation):
    """
    Base class for mutations that only apply to specific grammar rules.
    This prevents 'blind' mutations on incompatible node types.
    """

    def __init__(self, target_rule_types: list[str]):
        self.target_rule_types = target_rule_types

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if node.type not in self.target_rule_types:
            return False
        return self.apply_grammar_mutation(node, rng)

    @abstractmethod
    def apply_grammar_mutation(self, node: AstNode, rng: random.Random) -> bool:
        """Apply the specific mutation known to be safe for this rule type."""
        pass


# AST Token Operation Interfaces
class TokenMutationOperation(ABC):
    """Base class for textual token mutations."""

    @abstractmethod
    def mutate(self, text: str, rng: random.Random) -> str:
        """Apply the mutation to the token and return the result."""
        pass


# Common AST Structure Operations
class ShuffleChildren(AstMutationOperation):
    """Randomly shuffles the order of a node's children"""

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if len(node.children) < 2:
            return False
        rng.shuffle(node.children)
        return True


class ReverseChildren(AstMutationOperation):
    """Reverses the order of a node's children"""

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if len(node.children) < 2:
            return False
        node.children.reverse()
        return True


class RotateChildren(AstMutationOperation):
    """Rotates children left by k positions."""

    def __init__(self, k: int = 1):
        self.k = k

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        n = len(node.children)
        if n < 2:
            return False
        k = self.k % n
        if k == 0:
            return False
        node.children = node.children[k:] + node.children[:k]
        return True


class SwapTwoChildren(AstMutationOperation):
    """Swaps any two randomly chosen children"""

    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        if len(node.children) < 2:
            return False
        i, j = rng.sample(range(len(node.children)), 2)
        node.children[i], node.children[j] = node.children[j], node.children[i]
        return True


class CommutativeSwap(GrammarAwareOperation):
    """
    Safely swaps operands of a binary expression (e.g., 1+2 -> 2+1)
    while keeping the operator in the middle.
    """

    def __init__(
        self, target_rule_types: list[str], left_idx: int = 0, right_idx: int = 2
    ):
        super().__init__(target_rule_types)
        self.left_idx = left_idx
        self.right_idx = right_idx

    def apply_grammar_mutation(self, node: AstNode, rng: random.Random) -> bool:
        if len(node.children) <= max(self.left_idx, self.right_idx):
            return False
        node.children[self.left_idx], node.children[self.right_idx] = (
            node.children[self.right_idx],
            node.children[self.left_idx],
        )
        return True


class GrammarOperations(ABC):
    """Shared mutation engine for ASTs."""

    def __init__(self, rng_seed: int | None = None, validity_mode: int = 0):
        self.rng = random.Random(rng_seed)
        self.validity_mode = ValidityMode(validity_mode)

    # Tree Utilities
    def clone(self, node: AstNode) -> AstNode:
        """Deep-clone an entire AST subtre"""
        if node is None:
            return None
        return AstNode(
            node.type,
            children=[self.clone(child) for child in node.children],
            value=node.value,
        )

    def replace_subtree(self, root: AstNode, new_subtree: AstNode) -> bool:
        """
        Replace a randomly chosen non-root subtree with a new one.
        Uses weighted selection (internal nodes get higher weight).
        """
        nodes = list(self.iter_nodes(root))
        if len(nodes) <= 1:
            return False

        node, parent, index = self._weighted_choice(nodes[1:])  # avoid root

        if parent is None or index is None:
            return False

        parent.children[index] = self.clone(new_subtree)
        return True

    def _weighted_choice(self, nodes):
        weights = []
        for node, _, _ in nodes:
            weights.append(2.0 if not node.children else 1.0)
        return self.rng.choices(nodes, weights=weights, k=1)[0]

    def iter_nodes(
        self,
        root: AstNode,
        parent: AstNode | None = None,
        index: int | None = None,
    ) -> Iterator[tuple[AstNode, AstNode | None, int | None]]:
        """Depth-first iterator yielding (node, parent, child_index)."""
        stack: list[tuple[AstNode, AstNode | None, int | None]] = [(root, None, None)]
        while stack:
            current, parent, index = stack.pop()
            yield current, parent, index
            for i, child in reversed(list(enumerate(current.children))):
                stack.append((child, current, i))

    def find_nodes(
        self,
        root: AstNode,
        predicate: Callable[[AstNode], bool] | None = None,
    ) -> list[AstNode]:
        """Return all nodes matching an optional predicate."""
        return [
            node
            for node, _, _ in self.iter_nodes(root)
            if predicate is None or predicate(node)
        ]

    def leaf_nodes(self, root: AstNode) -> list[AstNode]:
        """Return only terminal nodes."""
        return [node for node, _, _ in self.iter_nodes(root) if not node.children]

    def internal_nodes(self, root: AstNode) -> list[AstNode]:
        """Return only nodes that have children."""
        return [node for node, _, _ in self.iter_nodes(root) if node.children]

    def is_leaf(self, node: AstNode) -> bool:
        """Check if a node has no children."""
        return not node.children

    def should_produce_malformed(self) -> bool:
        """Decide whether to produce malformed output based on validity mode."""
        if self.validity_mode == ValidityMode.WELL_FORMED:
            return False
        elif self.validity_mode == ValidityMode.SLIGHTLY_MALFORMED:
            return self.rng.random() < 0.25  # ~25% chance
        else:  # HEAVILY_MALFORMED
            return self.rng.random() < 0.70  # ~70% chance
        return False

    def apply_type_aware_crossover(self, root: AstNode) -> bool:
        """
        Swaps two subtrees of the exact same grammar rule type.
        """
        internal_nodes = self.internal_nodes(root)
        if len(internal_nodes) < 2:
            return False
        # Pick a target to be replaced
        target_node = self.rng.choice(internal_nodes)
        # Find all other nodes of the same type
        matching_nodes = self.find_nodes(
            root,
            predicate=lambda n: n.type == target_node.type and n is not target_node,
        )
        if not matching_nodes:
            return False
        # Clone donor and overwrite target's attributes
        donor_node = self.rng.choice(matching_nodes)
        donor_clone = self.clone(donor_node)
        target_node.children = donor_clone.children
        target_node.value = donor_clone.value
        return True

    # Public API
    def mutate(self, root: AstNode, structure_bias: float = 0.5) -> AstNode:
        """Perform ONE mutation on a cloned AST."""
        mutated = self.clone(root)
        assert mutated is not None

        if self.rng.random() < structure_bias:
            if not self.apply_structure_mutation(mutated):
                self.apply_token_mutation(mutated)
        else:
            if not self.apply_token_mutation(mutated):
                self.apply_structure_mutation(mutated)

        return mutated

    def mutate_n(
        self, root: AstNode, count: int = 1, structure_bias: float = 0.5
    ) -> AstNode:
        current = root
        for _ in range(count):
            current = self.mutate(current, structure_bias=structure_bias)
        return current

    # Grammar hooks
    @abstractmethod
    def apply_structure_mutation(self, root: AstNode) -> bool:
        """Apply one structural mutation. Return True if anything changed."""
        raise NotImplementedError

    @abstractmethod
    def apply_token_mutation(self, root: AstNode) -> bool:
        """Apply one token mutation. Return True if anything changed."""
        raise NotImplementedError

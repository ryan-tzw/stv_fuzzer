"""
The core interfaces and shared utilities for mutating Abstract Syntax Trees (ASTs).
It supports two mutation categories: Structural mutations & Token mutations
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import random
from typing import Callable, Iterator

from ..astBuilder import AstNode


# AST Structural Operation Interfaces
class AstMutationOperation(ABC):
    """Base class for AST structure mutations."""

    @abstractmethod
    def mutate(self, node: AstNode, rng: random.Random) -> bool:
        """Apply the mutation to the AST node in-place. Return True if successful."""
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


class GrammarOperations(ABC):
    """Shared mutation engine for ASTs."""

    def __init__(self, rng_seed: int | None = None):
        self.rng = random.Random(rng_seed)

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

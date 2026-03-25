"""Grammar-aware tree mutation via same-symbol subtree replacement."""

import random

from fuzzer.grammar.fragments import FragmentPool
from fuzzer.grammar.serializer import serialize_tree
from fuzzer.grammar.tree import Node


def mutate_tree(
    root: Node, pool: FragmentPool, rng: random.Random | None = None
) -> Node | None:
    """Replace one subtree with a same-symbol fragment from the pool."""
    return GrammarMutator(rng=rng).mutate_tree(root, pool)


class GrammarMutator:
    """Stateful wrapper for grammar-aware tree mutation."""

    def __init__(self, rng: random.Random | None = None):
        self._rng = rng or random.Random()

    def mutate_tree(self, root: Node, pool: FragmentPool) -> Node | None:
        candidates: list[tuple[Node, list[Node]]] = []
        for node in _collect_nodes(root):
            compatible = [
                fragment
                for fragment in pool.get(node.symbol)
                if not _serialize_equivalent(fragment, node)
            ]
            if compatible:
                candidates.append((node, compatible))

        if not candidates:
            return None

        target, replacements = self._rng.choice(candidates)
        replacement = self._rng.choice(replacements)
        return _replace_target(root, target, _clone_node(replacement))


def _clone_node(node: Node) -> Node:
    return Node(
        symbol=node.symbol,
        children=[_clone_node(child) for child in node.children],
        text=node.text,
    )


def _collect_nodes(root: Node) -> list[Node]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_collect_nodes(child))
    return nodes


def _replace_target(root: Node, target: Node, replacement: Node) -> Node:
    if root is target:
        return _clone_node(replacement)
    return Node(
        symbol=root.symbol,
        children=[
            _replace_target(child, target, replacement) for child in root.children
        ],
        text=root.text,
    )


def _serialize_equivalent(a: Node, b: Node) -> bool:
    return serialize_tree(a) == serialize_tree(b)

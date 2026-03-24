from __future__ import annotations

import random
from collections.abc import Iterable, Sequence

from .generator import GrammarGenerator
from .spec import GrammarSpec
from .tree import DerivationNode, LITERAL_SYMBOL


class GrammarTreeMutator:
    def __init__(self, spec: GrammarSpec, generator: GrammarGenerator) -> None:
        self._spec = spec
        self._generator = generator

    def mutate(
        self,
        tree: DerivationNode,
        donor_trees: Sequence[DerivationNode] | None = None,
    ) -> DerivationNode:
        donor_trees = donor_trees or []
        working = tree.clone()
        mutable_paths = [
            path
            for path, node in _walk(working)
            if self._is_mutable_symbol(node.symbol)
        ]

        if not mutable_paths:
            return self._generator.generate()

        operations = [self._replace_subtree]
        if any(
            _node_at(working, path).symbol in self._spec.terminal_generators
            for path in mutable_paths
        ):
            operations.append(self._regenerate_terminal)
        if donor_trees:
            operations.append(self._crossover)

        operation = random.choice(operations)
        return operation(working, mutable_paths, donor_trees)

    def _replace_subtree(
        self,
        tree: DerivationNode,
        mutable_paths: Sequence[tuple[int, ...]],
        donor_trees: Sequence[DerivationNode],
    ) -> DerivationNode:
        del donor_trees
        target_path = random.choice(list(mutable_paths))
        target = _node_at(tree, target_path)
        replacement = self._generator.generate_symbol(target.symbol)
        return _replace_at(tree, target_path, replacement)

    def _regenerate_terminal(
        self,
        tree: DerivationNode,
        mutable_paths: Sequence[tuple[int, ...]],
        donor_trees: Sequence[DerivationNode],
    ) -> DerivationNode:
        del donor_trees
        terminal_paths = [
            path
            for path in mutable_paths
            if _node_at(tree, path).symbol in self._spec.terminal_generators
        ]
        if not terminal_paths:
            return self._replace_subtree(tree, mutable_paths, ())
        target_path = random.choice(terminal_paths)
        target = _node_at(tree, target_path)
        replacement = self._generator.generate_symbol(target.symbol)
        return _replace_at(tree, target_path, replacement)

    def _crossover(
        self,
        tree: DerivationNode,
        mutable_paths: Sequence[tuple[int, ...]],
        donor_trees: Sequence[DerivationNode],
    ) -> DerivationNode:
        target_path = random.choice(list(mutable_paths))
        target = _node_at(tree, target_path)
        donor_matches = [
            node.clone()
            for donor in donor_trees
            for _, node in _walk(donor)
            if node.symbol == target.symbol
        ]
        if not donor_matches:
            return self._replace_subtree(tree, mutable_paths, donor_trees)
        replacement = random.choice(donor_matches)
        return _replace_at(tree, target_path, replacement)

    def _is_mutable_symbol(self, symbol: str) -> bool:
        return symbol != LITERAL_SYMBOL and (
            self._spec.is_nonterminal(symbol) or self._spec.is_terminal(symbol)
        )


def _walk(
    node: DerivationNode, path: tuple[int, ...] = ()
) -> Iterable[tuple[tuple[int, ...], DerivationNode]]:
    yield path, node
    for index, child in enumerate(node.children):
        yield from _walk(child, path + (index,))


def _node_at(root: DerivationNode, path: Sequence[int]) -> DerivationNode:
    node = root
    for index in path:
        node = node.children[index]
    return node


def _replace_at(
    root: DerivationNode, path: Sequence[int], replacement: DerivationNode
) -> DerivationNode:
    if not path:
        return replacement

    parent = _node_at(root, path[:-1])
    parent.children[path[-1]] = replacement
    return root

"""Grammar-aware tree mutation via same-symbol subtree replacement."""

import random
from dataclasses import dataclass

from fuzzer.grammar.coverage import GrammarCoverage
from fuzzer.grammar.fragments import FragmentPool
from fuzzer.grammar.serializer import serialize_tree
from fuzzer.grammar.tree import Node


@dataclass
class GrammarMutationConfig:
    """Base config. The adaptive version will modify these values over time."""

    min_mutations: int = 2
    max_mutations: int = 5
    splice_prob: float = 0.42
    recursive_prob: float = 0.48
    recursion_depth_chance: float = 0.65


class AdaptiveGrammarMutationConfig(GrammarMutationConfig):
    """Dynamic version — automatically adapts probabilities based on fuzzing progress."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._last_adapt_inputs: int = 0

    def adapt(self) -> None:
        """Adapt parameters based on how many inputs we have seen so far.
        Early phase: very aggressive.
        Later phase: more focused / less aggressive."""
        current = GrammarCoverage.get_global_total_inputs()
        if current == self._last_adapt_inputs:
            return

        self._last_adapt_inputs = current

        if current < 500:
            self.min_mutations = 3
            self.max_mutations = 7
            self.splice_prob = 0.55
            self.recursive_prob = 0.65
            self.recursion_depth_chance = 0.75
        elif current < 2000:
            self.min_mutations = 2
            self.max_mutations = 5
            self.splice_prob = 0.45
            self.recursive_prob = 0.50
            self.recursion_depth_chance = 0.68
        else:
            self.min_mutations = 1
            self.max_mutations = 3
            self.splice_prob = 0.30
            self.recursive_prob = 0.35
            self.recursion_depth_chance = 0.55


def mutate_tree(
    root: Node,
    pool: FragmentPool,
    coverage: GrammarCoverage | None = None,
    rng: random.Random | None = None,
    num_mutations: int = 1,
    allow_splice: bool = False,
    recursive_prob: float = 0.0,
) -> Node | None:
    """Replace one subtree with a same-symbol fragment from the pool."""
    return GrammarMutator(rng=rng, coverage=coverage).mutate_tree(
        root, pool, num_mutations, allow_splice, recursive_prob
    )


class GrammarMutator:
    """Stateful wrapper for grammar-aware tree mutation."""

    def __init__(
        self,
        rng: random.Random | None = None,
        coverage: GrammarCoverage | None = None,
        config: AdaptiveGrammarMutationConfig | None = None,
    ):
        self._rng = rng or random.Random()
        self.coverage = coverage or GrammarCoverage()
        self.config = config or AdaptiveGrammarMutationConfig()

    def mutate_tree(
        self,
        root: Node,
        pool: FragmentPool,
        num_mutations: int | None = None,
        allow_splice: bool = True,
        recursive_prob: float | None = None,
    ) -> Node | None:
        """Perform 1 or more coverage-guided subtree replacements."""
        self.config.adapt()
        if num_mutations is None:
            num_mutations = self._rng.randint(
                self.config.min_mutations, self.config.max_mutations
            )
        if recursive_prob is None:
            recursive_prob = self.config.recursive_prob
        current = root
        mutated = False
        for _ in range(num_mutations):
            if self._rng.random() < recursive_prob:
                new_tree = self._single_replacement(current, pool, allow_splice)
                if new_tree and self._rng.random() < self.config.recursion_depth_chance:
                    new_tree = self.mutate_tree(
                        new_tree, pool, 1, allow_splice, recursive_prob * 0.75
                    )
            else:
                new_tree = self._single_replacement(current, pool, allow_splice)
            if new_tree is None:
                break
            current = new_tree
            mutated = True
        return current if mutated else None

    def _single_replacement(
        self, root: Node, pool: FragmentPool, allow_splice: bool
    ) -> Node | None:
        if allow_splice and self._rng.random() < self.config.splice_prob:
            return self._large_splice(root, pool)

        candidates: list[tuple[float, Node, list[Node]]] = []
        for node in _collect_nodes(root):
            compatible = [
                fragment
                for fragment in pool.get(node.symbol)
                if not _serialize_equivalent(fragment, node)
            ]
            if compatible:
                weight = self.coverage.get_symbol_weight(node.symbol)
                candidates.append((weight, node, compatible))

        if not candidates:
            return None

        total_weight = sum(w for w, _, _ in candidates)
        r = self._rng.uniform(0, total_weight)
        current = 0.0
        for weight, target, replacements in candidates:
            current += weight
            if current >= r:
                break
        else:
            _, target, replacements = self._rng.choice(candidates)
        replacement = self._rng.choice(replacements)
        return _replace_target(root, target, _clone_node(replacement))

    def _large_splice(self, root: Node, pool: FragmentPool) -> Node | None:
        """Large subtree splice — prefers bigger fragments for stronger changes."""
        candidates: list[tuple[float, Node, list[Node]]] = []
        for node in _collect_nodes(root):
            fragments = pool.get(node.symbol)
            if len(fragments) > 1:
                # Bias toward larger fragments
                weights = [len(f.children) + 1 for f in fragments]
                total = sum(weights)
                weights = [w / total for w in weights]
                chosen = self._rng.choices(fragments, weights=weights, k=1)[0]
                if not _serialize_equivalent(chosen, node):
                    candidates.append((1.0, node, [chosen]))
        if not candidates:
            return None
        target, replacements = (
            self._rng.choice(candidates)[1],
            self._rng.choice(candidates)[2],
        )
        return _replace_target(root, target, _clone_node(replacements[0]))


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

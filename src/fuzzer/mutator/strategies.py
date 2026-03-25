"""Mutator strategy registry composed from string and tree domains."""

from collections.abc import Callable

from fuzzer.mutator.base import MutationStrategy
from fuzzer.mutator.string.strategies import RandomSingleStrategy
from fuzzer.mutator.tree.strategies import GrammarSubtreeStrategy


STRATEGY_FACTORIES: dict[str, Callable[[], MutationStrategy]] = {
    "random_single": RandomSingleStrategy,
    "grammar_subtree": GrammarSubtreeStrategy,
}

AVAILABLE_STRATEGIES: tuple[str, ...] = tuple(STRATEGY_FACTORIES.keys())


def build_strategy(name: str) -> MutationStrategy:
    """Build and return a mutation strategy by name."""
    try:
        return STRATEGY_FACTORIES[name]()
    except KeyError as exc:
        available = ", ".join(sorted(STRATEGY_FACTORIES))
        raise ValueError(
            f"Unknown mutation strategy: {name!r}. Available: {available}"
        ) from exc

"""Mutator strategy registry with generic operation-selection strategies."""

from collections.abc import Callable
from typing import Any

from fuzzer.mutator.base import MutationOperation, MutationStrategy
from fuzzer.mutator.selectors import RandomSingleStrategy
from fuzzer.mutator.tree.operations import GrammarSubtreeReplace


STRATEGY_FACTORIES: dict[str, Callable[..., MutationStrategy]] = {
    "random_single": RandomSingleStrategy,
}

AVAILABLE_STRATEGIES: tuple[str, ...] = tuple(STRATEGY_FACTORIES.keys())


def build_strategy(name: str, **context: Any) -> MutationStrategy:
    """Build and return a mutation strategy by name."""
    try:
        operations = context.get("operations")
        if operations is None:
            operations = _build_default_operations(context)
        return STRATEGY_FACTORIES[name](operations=operations)
    except KeyError as exc:
        available = ", ".join(sorted(STRATEGY_FACTORIES))
        raise ValueError(
            f"Unknown mutation strategy: {name!r}. Available: {available}"
        ) from exc


def _build_default_operations(context: dict[str, Any]) -> list[MutationOperation]:
    grammar_name = context.get("grammar_name", "ipv4")
    return [GrammarSubtreeReplace(grammar_name=grammar_name)]

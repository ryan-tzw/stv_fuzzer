"""Mutator strategy builder over selector registry and operation wiring."""

from typing import Any

from fuzzer.grammar.coverage import GrammarCoverage
from fuzzer.mutator.tree.grammar_mutator import AdaptiveGrammarMutationConfig
from fuzzer.mutator.base import MutationOperation, MutationStrategy
from fuzzer.mutator.selectors import SELECTOR_FACTORIES
from fuzzer.mutator.string.operations import (
    DeleteChar,
    DuplicateChar,
    InsertRandomChar,
    RandomiseChar,
)
from fuzzer.mutator.tree.operations import (
    AlternativeSwitch,
    LargeSubtreeSplice,
    GrammarSubtreeReplace,
    MultiGrammarSubtreeReplace,
    RecursiveGrammarMutate,
    SubtreeDelete,
    SubtreeDuplicate,
    TerminalMutate,
)


STRATEGY_FACTORIES = SELECTOR_FACTORIES

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
    config = AdaptiveGrammarMutationConfig(
        min_mutations=2,
        max_mutations=6,
        splice_prob=0.50,
        recursive_prob=0.55,
        recursion_depth_chance=0.70,
    )
    # Global shared coverage
    shared_coverage = GrammarCoverage()
    return [
        GrammarSubtreeReplace(grammar_name=grammar_name, coverage=shared_coverage),
        MultiGrammarSubtreeReplace(
            grammar_name=grammar_name, config=config, coverage=shared_coverage
        ),
        TerminalMutate(grammar_name=grammar_name),
        SubtreeDelete(grammar_name=grammar_name),
        SubtreeDuplicate(grammar_name=grammar_name),
        AlternativeSwitch(grammar_name=grammar_name),
        LargeSubtreeSplice(
            grammar_name=grammar_name, config=config, coverage=shared_coverage
        ),
        RecursiveGrammarMutate(
            grammar_name=grammar_name, config=config, coverage=shared_coverage
        ),
        RandomiseChar(),
        DeleteChar(),
        InsertRandomChar(),
        DuplicateChar(),
    ]

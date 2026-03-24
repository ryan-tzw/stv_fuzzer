"""
Mutator: applies a mutation strategy to produce a mutated input.
"""

import random
from .strategies import MutationStrategy, BlindRandomStrategy


class Mutator:
    """Takes any MutationStrategy and applies it with optional seeding."""

    def __init__(
        self, strategy: MutationStrategy | None = None, rng_seed: int | None = None
    ):
        self.strategy = strategy or BlindRandomStrategy()
        self.rng = random.Random(rng_seed)

    def mutate(self, data: str, depth: int = 1) -> str:
        """Perform 'depth' mutation using the selected strategy."""
        return self.strategy.apply(data, self.rng, depth)

    def set_rng_seed(self, rng_seed: int):
        """Update the seed for deterministic behavior."""
        self.rng.seed(rng_seed)


if __name__ == "__main__":
    import argparse
    import random
    from pathlib import Path
    from .strategies import BlindRandomStrategy, GrammarStrategy

    parser = argparse.ArgumentParser(description="Test the mutator on an input string")
    parser.add_argument("input", help="Input string to mutate")
    parser.add_argument(
        "--grammar",
        help="Specify grammar (json, ip, arithmetic, or any other ANTLR grammar)",
    )
    parser.add_argument(
        "--depth", "-d", type=int, default=1, help="Number of mutations per iteration"
    )
    parser.add_argument(
        "--rng_seed", type=int, help="Seed for the random number generator"
    )
    args = parser.parse_args()

    ANTLR_PATH = (Path(__file__).parent.parent.parent / "grammars" / "antlr").resolve()
    selected_strategy = None

    if args.grammar:
        try:
            from ...grammars.parser.parser import create_parser
            from ...grammars.grammarRegistry import get_registry
            from ...grammars.operations import GenericGrammarOperations

            grammar_parser = create_parser(args.grammar, ANTLR_PATH)

            # Try to use custom operations from registry, fall back to generic
            registry = get_registry()
            grammar_config = registry.get(args.grammar)

            if grammar_config and grammar_config.get("operations_class"):
                grammar_ops = grammar_config["operations_class"]()
            else:
                grammar_ops = GenericGrammarOperations()

            selected_strategy = GrammarStrategy(grammar_parser, grammar_ops)
            print(f"[*] Using Grammar Strategy for: {args.grammar}")
        except Exception as e:
            print(f"[!] Could not load grammar '{args.grammar}': {e}")
            print("[*] Falling back to Blind mutation")

    if not selected_strategy:
        selected_strategy = BlindRandomStrategy()
        print("[*] Using Blind Random Strategy")

    mutator = Mutator(strategy=selected_strategy, rng_seed=args.rng_seed)
    result = mutator.mutate(args.input)
    print(f"Original: {args.input}")
    print(f"Mutated:  {result}")

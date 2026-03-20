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

    try:
        from ...grammars.parser.parser import ipParser, jsonParser
        from ...grammars.operations.ipOperations import IpGrammarOperations
        from ...grammars.operations.jsonOperations import JsonGrammarOperations
    except ImportError:
        ipParser = jsonParser = None
        IpGrammarOperations = JsonGrammarOperations = None

    parser = argparse.ArgumentParser(description="Test the mutator on an input string")
    parser.add_argument("input", help="Input string to mutate")
    parser.add_argument(
        "--grammar",
        choices=["json", "ip"],
        help="Specify a grammar-aware strategy (default: blind mutation)",
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

    if args.grammar == "json":
        if jsonParser and JsonGrammarOperations:
            parser = jsonParser(ANTLR_PATH)
            ops = JsonGrammarOperations()
            selected_strategy = GrammarStrategy(parser, ops)
            print("[*] Using JSON Grammar Strategy")
        else:
            print(
                "[!] JSON parser components not found. Falling back to Blind mutation."
            )
    elif args.grammar == "ip":
        if ipParser and IpGrammarOperations:
            parser = ipParser(ANTLR_PATH)
            ops = IpGrammarOperations()
            selected_strategy = GrammarStrategy(parser, ops)
            print("[*] Using IP Grammar Strategy")
        else:
            print("[!] IP parser components not found. Falling back to Blind mutation.")

    if not selected_strategy:
        selected_strategy = BlindRandomStrategy()
        print("[*] Using Blind Random Strategy")

    mutator = Mutator(strategy=selected_strategy, rng_seed=args.rng_seed)
    result = mutator.mutate(args.input)
    print(f"Original: {args.input}")
    print(f"Mutated:  {result}")

"""Tree-domain mutation operations exposed through string mutate interface."""

from fuzzer.grammar.fragments import FragmentPool
from fuzzer.grammar.parser import parse_input
from fuzzer.grammar.serializer import serialize_tree
from fuzzer.grammar.loader import load_parser
from fuzzer.mutator.base import MutationOperation
from fuzzer.mutator.tree.grammar_mutator import GrammarMutator


class GrammarSubtreeReplace(MutationOperation):
    """Mutate text by parsing to a Node tree and replacing one subtree."""

    def __init__(self, grammar_name: str = "ipv4"):
        self.grammar_name = grammar_name
        self._parser = load_parser(self.grammar_name)
        self._pool = FragmentPool()
        self._mutator = GrammarMutator()

    def mutate(self, data: str) -> str:
        try:
            parsed = parse_input(self._parser, data)
            if not parsed.success or parsed.tree is None:
                return data

            self._pool.add_tree(parsed.tree)
            mutated = self._mutator.mutate_tree(parsed.tree, self._pool)
            if mutated is None:
                return data

            return serialize_tree(mutated)
        except Exception:
            return data

"""Tree-domain mutation operations exposed through string mutate interface."""

import random

from fuzzer.grammar.fragments import FragmentPool
from fuzzer.grammar.loader import load_parser
from fuzzer.grammar.parser import parse_input
from fuzzer.grammar.serializer import serialize_tree
from fuzzer.grammar.tree import Node
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


class TerminalMutate(MutationOperation):
    """Mutate one terminal leaf text in a parsed Node tree."""

    def __init__(self, grammar_name: str = "ipv4", rng: random.Random | None = None):
        self.grammar_name = grammar_name
        self._parser = load_parser(self.grammar_name)
        self._rng = rng or random.Random()

    def mutate(self, data: str) -> str:
        try:
            parsed = parse_input(self._parser, data)
            if not parsed.success or parsed.tree is None:
                return data

            leaves = _collect_terminal_paths(parsed.tree)
            if not leaves:
                return data

            path, leaf = self._rng.choice(leaves)
            mutated_text = _mutate_terminal_text(
                leaf.symbol, leaf.text or "", self._rng
            )
            if mutated_text == leaf.text:
                return data

            mutated_tree = _replace_leaf_at_path(parsed.tree, path, mutated_text)
            return serialize_tree(mutated_tree)
        except Exception:
            return data


def _collect_terminal_paths(root: Node) -> list[tuple[tuple[int, ...], Node]]:
    output: list[tuple[tuple[int, ...], Node]] = []

    def walk(node: Node, path: tuple[int, ...]) -> None:
        if node.is_terminal():
            output.append((path, node))
            return
        for idx, child in enumerate(node.children):
            walk(child, path + (idx,))

    walk(root, ())
    return output


def _replace_leaf_at_path(root: Node, path: tuple[int, ...], text: str) -> Node:
    if not path:
        return Node(symbol=root.symbol, children=[], text=text)

    child_index = path[0]
    rebuilt_children: list[Node] = []
    for idx, child in enumerate(root.children):
        if idx == child_index:
            rebuilt_children.append(_replace_leaf_at_path(child, path[1:], text))
        else:
            rebuilt_children.append(child)
    return Node(symbol=root.symbol, children=rebuilt_children, text=root.text)


def _mutate_terminal_text(symbol: str, text: str, rng: random.Random) -> str:
    mutator = _TERMINAL_MUTATORS.get(symbol)
    if mutator is not None:
        return mutator(text, rng)
    return _mutate_text_fallback(text, rng)


def _mutate_digit(text: str, rng: random.Random) -> str:
    choices = ["0", "9"] if rng.random() < 0.35 else [str(rng.randint(0, 9))]
    return rng.choice(choices)


def _mutate_octet(text: str, rng: random.Random) -> str:
    if rng.random() < 0.45:
        return str(rng.choice([0, 255, 256]))
    return str(rng.randint(0, 300))


def _mutate_hextet(text: str, rng: random.Random) -> str:
    if rng.random() < 0.2:
        width = 5
    else:
        width = rng.randint(1, 4)
    alphabet = "0123456789abcdefABCDEF"
    return "".join(rng.choice(alphabet) for _ in range(width))


def _mutate_signed_number(text: str, rng: random.Random) -> str:
    if rng.random() < 0.4:
        return rng.choice(["0", "-1", "999999999", "-999999999"])

    sign = rng.choice(["", "-", "+"])
    whole = str(rng.randint(0, 999999))
    if rng.random() < 0.35:
        frac = str(rng.randint(0, 9999))
        return f"{sign}{whole}.{frac}"
    return f"{sign}{whole}"


def _mutate_escaped_string(text: str, rng: random.Random) -> str:
    if rng.random() < 0.3:
        return '""'
    if rng.random() < 0.35:
        return '"a\\\\\\"b"'

    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-"
    length = rng.randint(0, 12)
    value = "".join(rng.choice(alphabet) for _ in range(length))
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _mutate_text_fallback(text: str, rng: random.Random) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    if not text:
        return rng.choice(alphabet)

    mode = rng.choice(["replace", "insert", "delete"])
    idx = rng.randrange(len(text))
    ch = rng.choice(alphabet)

    if mode == "replace":
        return text[:idx] + ch + text[idx + 1 :]
    if mode == "insert":
        return text[:idx] + ch + text[idx:]
    if len(text) == 1:
        return ch
    return text[:idx] + text[idx + 1 :]


_TERMINAL_MUTATORS = {
    "DIGIT": _mutate_digit,
    "OCTET": _mutate_octet,
    "HEXTET": _mutate_hextet,
    "SIGNED_NUMBER": _mutate_signed_number,
    "ESCAPED_STRING": _mutate_escaped_string,
}

"""Tree-domain mutation operations exposed through string mutate interface."""

import random
from dataclasses import dataclass

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


class SubtreeDelete(MutationOperation):
    """Delete one compatible subtree from a repeated structure."""

    def __init__(self, grammar_name: str = "ipv4", rng: random.Random | None = None):
        self.grammar_name = grammar_name
        self._parser = load_parser(self.grammar_name)
        self._rng = rng or random.Random()

    def mutate(self, data: str) -> str:
        try:
            parsed = parse_input(self._parser, data)
            if not parsed.success or parsed.tree is None:
                return data

            candidates = _collect_delete_candidates(parsed.tree)
            if not candidates:
                return data

            candidate = self._rng.choice(candidates)
            mutated_tree = _apply_delete(parsed.tree, candidate)
            mutated = serialize_tree(mutated_tree)
            return mutated if mutated != data else data
        except Exception:
            return data


class SubtreeDuplicate(MutationOperation):
    """Duplicate one compatible subtree from a repeated structure."""

    def __init__(self, grammar_name: str = "ipv4", rng: random.Random | None = None):
        self.grammar_name = grammar_name
        self._parser = load_parser(self.grammar_name)
        self._rng = rng or random.Random()

    def mutate(self, data: str) -> str:
        try:
            parsed = parse_input(self._parser, data)
            if not parsed.success or parsed.tree is None:
                return data

            candidates = _collect_duplicate_candidates(parsed.tree)
            if not candidates:
                return data

            candidate = self._rng.choice(candidates)
            mutated_tree = _apply_duplicate(parsed.tree, candidate)
            mutated = serialize_tree(mutated_tree)
            return mutated if mutated != data else data
        except Exception:
            return data


@dataclass(frozen=True)
class _DeleteCandidate:
    parent_path: tuple[int, ...]
    remove_indices: tuple[int, ...]


@dataclass(frozen=True)
class _DuplicateCandidate:
    parent_path: tuple[int, ...]
    insert_index: int
    nodes_to_insert: tuple[Node, ...]


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


def _clone_node(node: Node) -> Node:
    return Node(
        symbol=node.symbol,
        children=[_clone_node(child) for child in node.children],
        text=node.text,
    )


def _collect_parent_paths(root: Node) -> list[tuple[tuple[int, ...], Node]]:
    output: list[tuple[tuple[int, ...], Node]] = []

    def walk(node: Node, path: tuple[int, ...]) -> None:
        output.append((path, node))
        for idx, child in enumerate(node.children):
            walk(child, path + (idx,))

    walk(root, ())
    return output


def _collect_delete_candidates(root: Node) -> list[_DeleteCandidate]:
    candidates: list[_DeleteCandidate] = []
    for path, parent in _collect_parent_paths(root):
        candidates.extend(_json_delete_candidates(path, parent))
        if parent.symbol not in {"object", "array"}:
            candidates.extend(_generic_delete_candidates(path, parent))
    return candidates


def _collect_duplicate_candidates(root: Node) -> list[_DuplicateCandidate]:
    candidates: list[_DuplicateCandidate] = []
    for path, parent in _collect_parent_paths(root):
        candidates.extend(_json_duplicate_candidates(path, parent))
        if parent.symbol not in {"object", "array"}:
            candidates.extend(_generic_duplicate_candidates(path, parent))
    return candidates


def _json_item_indices(parent: Node) -> list[int]:
    if parent.symbol == "object":
        return [
            idx for idx, child in enumerate(parent.children) if child.symbol == "pair"
        ]
    if parent.symbol == "array":
        blocked = {"LSQB", "RSQB", "COMMA"}
        return [
            idx
            for idx, child in enumerate(parent.children)
            if child.symbol not in blocked
        ]
    return []


def _json_delete_candidates(
    path: tuple[int, ...], parent: Node
) -> list[_DeleteCandidate]:
    item_indices = _json_item_indices(parent)
    if not item_indices:
        return []

    candidates: list[_DeleteCandidate] = []
    for idx in item_indices:
        remove = {idx}
        if len(item_indices) > 1:
            if (
                idx + 1 < len(parent.children)
                and parent.children[idx + 1].symbol == "COMMA"
            ):
                remove.add(idx + 1)
            elif idx > 0 and parent.children[idx - 1].symbol == "COMMA":
                remove.add(idx - 1)
        candidates.append(
            _DeleteCandidate(parent_path=path, remove_indices=tuple(sorted(remove)))
        )
    return candidates


def _json_duplicate_candidates(
    path: tuple[int, ...], parent: Node
) -> list[_DuplicateCandidate]:
    item_indices = _json_item_indices(parent)
    if not item_indices:
        return []

    candidates: list[_DuplicateCandidate] = []
    for idx in item_indices:
        clone = _clone_node(parent.children[idx])
        comma = Node(symbol="COMMA", children=[], text=",")
        candidates.append(
            _DuplicateCandidate(
                parent_path=path,
                insert_index=idx + 1,
                nodes_to_insert=(comma, clone),
            )
        )
    return candidates


def _generic_delete_candidates(
    path: tuple[int, ...], parent: Node
) -> list[_DeleteCandidate]:
    groups: dict[str, list[int]] = {}
    for idx, child in enumerate(parent.children):
        if child.text is None:
            groups.setdefault(child.symbol, []).append(idx)

    candidates: list[_DeleteCandidate] = []
    for indices in groups.values():
        if len(indices) < 2:
            continue
        for idx in indices:
            candidates.append(_DeleteCandidate(parent_path=path, remove_indices=(idx,)))
    return candidates


def _generic_duplicate_candidates(
    path: tuple[int, ...], parent: Node
) -> list[_DuplicateCandidate]:
    groups: dict[str, list[int]] = {}
    for idx, child in enumerate(parent.children):
        if child.text is None:
            groups.setdefault(child.symbol, []).append(idx)

    candidates: list[_DuplicateCandidate] = []
    for indices in groups.values():
        if len(indices) < 2:
            continue
        for idx in indices:
            candidates.append(
                _DuplicateCandidate(
                    parent_path=path,
                    insert_index=idx + 1,
                    nodes_to_insert=(_clone_node(parent.children[idx]),),
                )
            )
    return candidates


def _apply_delete(root: Node, candidate: _DeleteCandidate) -> Node:
    def edit(children: list[Node]) -> list[Node]:
        remove = set(candidate.remove_indices)
        return [child for idx, child in enumerate(children) if idx not in remove]

    return _edit_children_at_path(root, candidate.parent_path, edit)


def _apply_duplicate(root: Node, candidate: _DuplicateCandidate) -> Node:
    def edit(children: list[Node]) -> list[Node]:
        before = list(children[: candidate.insert_index])
        after = list(children[candidate.insert_index :])
        inserted = [_clone_node(node) for node in candidate.nodes_to_insert]
        return before + inserted + after

    return _edit_children_at_path(root, candidate.parent_path, edit)


def _edit_children_at_path(
    root: Node,
    path: tuple[int, ...],
    edit: callable,
) -> Node:
    if not path:
        return Node(symbol=root.symbol, children=edit(root.children), text=root.text)

    child_index = path[0]
    rebuilt_children: list[Node] = []
    for idx, child in enumerate(root.children):
        if idx == child_index:
            rebuilt_children.append(_edit_children_at_path(child, path[1:], edit))
        else:
            rebuilt_children.append(child)

    return Node(symbol=root.symbol, children=rebuilt_children, text=root.text)


_TERMINAL_MUTATORS = {
    "DIGIT": _mutate_digit,
    "OCTET": _mutate_octet,
    "HEXTET": _mutate_hextet,
    "SIGNED_NUMBER": _mutate_signed_number,
    "ESCAPED_STRING": _mutate_escaped_string,
}

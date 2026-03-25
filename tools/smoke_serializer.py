"""Smoke-check for parse -> serialize round-trip."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _find_first_by_symbol(node, symbol):
    if node.symbol == symbol:
        return node
    for child in node.children:
        found = _find_first_by_symbol(child, symbol)
        if found is not None:
            return found
    return None


def main() -> int:
    from fuzzer.grammar.loader import load_parser
    from fuzzer.grammar.parser import parse_input
    from fuzzer.grammar.serializer import serialize_tree

    sample = "192.168.0.1"
    parser = load_parser("ipv4")
    result = parse_input(parser, sample)

    print(f"parse_success: {result.success}")
    if not result.success or result.tree is None:
        print("errors:")
        for error in result.errors:
            print(f"- {error}")
        return 1

    out = serialize_tree(result.tree)
    print(f"roundtrip: {out}")
    print(f"roundtrip_ok: {out == sample}")
    if out != sample:
        print("error: round-trip mismatch")
        return 1

    ipv4_node = _find_first_by_symbol(result.tree, "ipv4")
    if ipv4_node is None:
        print("error: could not find ipv4 subtree")
        return 1
    print(f"ipv4_subtree: {serialize_tree(ipv4_node)}")

    octet_node = _find_first_by_symbol(result.tree, "octet")
    if octet_node is None:
        print("error: could not find octet subtree")
        return 1
    print(f"octet_subtree: {serialize_tree(octet_node)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

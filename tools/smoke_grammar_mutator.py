"""Smoke-check for same-symbol grammar subtree replacement mutator."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> int:
    from fuzzer.grammar.fragments import FragmentPool
    from fuzzer.grammar.grammar_mutator import mutate_tree
    from fuzzer.grammar.loader import load_parser
    from fuzzer.grammar.parser import parse_input
    from fuzzer.grammar.serializer import serialize_tree

    parser = load_parser("ipv4")
    r1 = parse_input(parser, "192.168.0.1")
    r2 = parse_input(parser, "10.0.0.255")

    if not r1.success or r1.tree is None:
        print("error: failed to parse seed 1")
        print(r1.errors)
        return 1
    if not r2.success or r2.tree is None:
        print("error: failed to parse seed 2")
        print(r2.errors)
        return 1

    pool = FragmentPool()
    pool.add_tree(r1.tree)
    pool.add_tree(r2.tree)

    mutated = mutate_tree(r1.tree, pool)
    if mutated is None:
        print("error: no valid mutation was produced")
        return 1

    print(f"original: {serialize_tree(r1.tree)}")
    print(f"mutated:  {serialize_tree(mutated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

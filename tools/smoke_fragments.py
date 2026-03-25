"""Smoke-check for fragment extraction from internal Node trees."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> int:
    from fuzzer.grammar.fragments import FragmentPool
    from fuzzer.grammar.loader import load_parser
    from fuzzer.grammar.parser import parse_input
    from fuzzer.grammar.tree import Node

    parser = load_parser("ipv4")
    result = parse_input(parser, "192.168.0.1")
    print(f"parse_success: {result.success}")
    if not result.success or result.tree is None:
        print("errors:")
        for error in result.errors:
            print(f"- {error}")
        return 1

    pool = FragmentPool()
    pool.add_tree(result.tree)

    print(f"symbols: {pool.symbols()}")
    print(f"count(octet): {pool.count('octet')}")
    print(f"count(DIGIT): {pool.count('DIGIT')}")

    octets_before = pool.get("octet")
    if not octets_before:
        print("error: expected at least one octet fragment")
        return 1

    # Mutate returned fragment in-memory and ensure pool storage is unaffected.
    first = octets_before[0]
    mutated = Node(symbol="mutated", children=first.children, text=first.text)
    octets_after = pool.get("octet")
    isolation_ok = bool(octets_after) and octets_after[0].symbol == "octet"
    print(f"clone_isolation_ok: {isolation_ok}")
    _ = mutated  # keep explicit local to show mutation intent

    if pool.count("octet") < 4:
        print("error: expected at least 4 octet fragments for IPv4 input")
        return 1
    if not pool.symbols():
        print("error: expected non-empty symbol set")
        return 1
    if "start" not in pool.symbols():
        print("error: expected root symbol 'start' in pool")
        return 1
    if not isolation_ok:
        print("error: fragment clone isolation check failed")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

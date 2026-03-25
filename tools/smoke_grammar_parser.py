"""Smoke-check for grammar parser bridge (Lark -> internal Node)."""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> int:
    from fuzzer.grammar.loader import load_parser
    from fuzzer.grammar.parser import parse_input

    cli = argparse.ArgumentParser(description="Smoke test grammar parser bridge")
    cli.add_argument("--input", default="192.168.0.1", help="Input to parse")
    args = cli.parse_args()

    parser = load_parser("ipv4")
    result = parse_input(parser, args.input)

    print(f"success: {result.success}")

    if not result.success:
        print("errors:")
        for error in result.errors:
            print(f"- {error}")
        return 1

    if result.tree is None:
        print("errors:")
        print("- parse reported success but tree is missing")
        return 1

    print(f"root: {result.tree.symbol}")
    print(f"root_children: {len(result.tree.children)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

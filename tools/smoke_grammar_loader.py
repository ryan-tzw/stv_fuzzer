"""Smoke-check for Lark grammar loader."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> int:
    from fuzzer.grammar.loader import load_parser

    parser = load_parser("ipv4")
    print("loaded: True")
    print(f"parser: {type(parser).__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Smoke-check for grammar_subtree strategy via core Mutator path."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> int:
    from fuzzer.mutator import Mutator, build_strategy

    mutator = Mutator(strategy=build_strategy("grammar_subtree"))

    seed = "192.168.0.1"
    outputs = []
    for _ in range(10):
        outputs.append(mutator.mutate(seed))

    unique_outputs = sorted(set(outputs))
    print(f"seed: {seed}")
    print(f"unique_outputs: {len(unique_outputs)}")
    for value in unique_outputs[:10]:
        print(value)

    if not unique_outputs:
        print("error: no outputs generated")
        return 1
    if any(not isinstance(value, str) for value in unique_outputs):
        print("error: non-string output found")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

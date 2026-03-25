"""Smoke-check for grammar_subtree strategy via core Mutator path."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> int:
    from fuzzer.mutator import Mutator, build_strategy

    cases = [
        ("ipv4", "192.168.0.1"),
        ("ipv6", "2001:db8::1"),
        ("json", '{"a":1,"b":[2,3]}'),
    ]
    failed = False

    for grammar_name, seed in cases:
        try:
            mutator = Mutator(
                strategy=build_strategy("grammar_subtree", grammar_name=grammar_name)
            )
        except Exception as exc:
            failed = True
            print(f"[{grammar_name}] error: failed to build strategy: {exc}")
            print()
            continue

        outputs = []
        try:
            for _ in range(10):
                outputs.append(mutator.mutate(seed))
        except Exception as exc:
            failed = True
            print(f"[{grammar_name}] error: mutation run failed: {exc}")
            print()
            continue

        unique_outputs = sorted(set(outputs))
        print(f"[{grammar_name}] seed: {seed}")
        print(f"[{grammar_name}] unique_outputs: {len(unique_outputs)}")
        for value in unique_outputs[:10]:
            print(value)
        print()

        if not unique_outputs:
            failed = True
            print(f"error: no outputs generated for {grammar_name}")
        if any(not isinstance(value, str) for value in unique_outputs):
            failed = True
            print(f"error: non-string output found for {grammar_name}")

    if failed:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

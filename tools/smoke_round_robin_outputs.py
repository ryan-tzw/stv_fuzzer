def main() -> int:
    import argparse
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from fuzzer.mutator import Mutator, build_strategy

    parser = argparse.ArgumentParser(
        description="Round-robin smoke test across ipv4/ipv6/json."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of outputs per grammar (default: 10)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tools/smoke_round_robin_outputs.txt"),
        help="Output file path (default: tools/smoke_round_robin_outputs.txt)",
    )
    args = parser.parse_args()

    cases = [
        ("ipv4", "192.168.0.1"),
        ("ipv6", "2001:db8::1"),
        ("json", '{"a":1,"b":[2,3]}'),
    ]

    lines: list[str] = []
    for grammar_name, seed in cases:
        strategy = build_strategy("round_robin", grammar_name=grammar_name)
        mutator = Mutator(strategy=strategy)

        lines.append(f"[{grammar_name}] seed: {seed}")
        for i in range(args.count):
            mutated = mutator.mutate(seed)
            lines.append(f"{i + 1:2d}. {mutated}")
        lines.append("")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote smoke output to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

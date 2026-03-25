def main() -> int:
    import random
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from fuzzer.grammar.generator import generate_from_grammar
    from fuzzer.grammar.loader import load_parser
    from fuzzer.grammar.parser import parse_input

    rng = random.Random(1337)
    cases = ("ipv4", "ipv6", "json")
    sample_count = 25
    failed = False

    for grammar_name in cases:
        parser = load_parser(grammar_name)
        parseable = 0
        generated: list[str] = []

        try:
            for _ in range(sample_count):
                value = generate_from_grammar(
                    grammar_name,
                    rng=rng,
                    max_depth=8,
                )
                generated.append(value)
                result = parse_input(parser, value)
                if result.success:
                    parseable += 1
        except Exception as exc:
            failed = True
            print(f"[{grammar_name}] generation error: {exc}")
            print()
            continue

        print(f"[{grammar_name}] generated={len(generated)} parseable={parseable}")
        for sample in generated[:5]:
            print(sample)
        print()

        if parseable == 0:
            failed = True
            print(f"[{grammar_name}] error: no parseable outputs")
            print()

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

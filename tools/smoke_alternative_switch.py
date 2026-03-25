def main() -> int:
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from fuzzer.grammar.loader import load_parser
    from fuzzer.grammar.parser import parse_input
    from fuzzer.mutator.tree.operations import AlternativeSwitch

    cases = [
        ("json", '{"a":1,"b":[2,3]}'),
        ("ipv6", "2001:db8::1"),
        ("ipv4", "192.168.0.1"),
    ]

    retries = 50
    must_change = {"json", "ipv6"}
    failed = False

    for grammar_name, seed in cases:
        parser = load_parser(grammar_name)
        operation = AlternativeSwitch(grammar_name=grammar_name)

        outputs: list[str] = []
        parseable = 0
        for _ in range(retries):
            value = operation.mutate(seed)
            outputs.append(value)
            if parse_input(parser, value).success:
                parseable += 1

        unique_outputs = sorted(set(outputs))
        changed = any(value != seed for value in unique_outputs)
        non_string = any(not isinstance(value, str) for value in unique_outputs)

        print(f"[{grammar_name}] seed: {seed}")
        print(f"[{grammar_name}] unique_outputs: {len(unique_outputs)}")
        print(f"[{grammar_name}] changed: {changed}")
        print(f"[{grammar_name}] parseable: {parseable}/{len(outputs)}")
        for sample in unique_outputs[:10]:
            print(sample)
        print()

        if non_string:
            failed = True
            print(f"[{grammar_name}] error: non-string output encountered")
            print()

        if grammar_name in must_change and not changed:
            failed = True
            print(f"[{grammar_name}] error: no alternative-switch change observed")
            print()

        if parseable == 0:
            failed = True
            print(f"[{grammar_name}] error: parseability ratio is zero")
            print()

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
